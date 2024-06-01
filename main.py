from flask import Flask, request, jsonify, session, Response
from openai import OpenAI
from portkey_ai import PORTKEY_GATEWAY_URL, createHeaders, Portkey
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
from collections import deque
from bson import ObjectId
import os
import time
import json
import google.generativeai as genai

from configs import gemini_safety_settings, gemini_generation_config
from utils import generate_chat_prompt, generate_conversation_prompt, initialize_model
import hashlib

load_dotenv()

portkey = Portkey(
    api_key=os.getenv('PORTKEY_API_KEY'),
    virtual_key=os.getenv('PORTKEY_VIRTUAL_KEY')
)

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))


uri = "mongodb+srv://uditj:Udit%406129@cluster0.ytkma3f.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))
db = client['Cluster0']  # Replace 'Cluster0' with your database name
bot_collection = db['bot']
conversation_collection = db['conversation']
user_collection = db['user']

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Set a secret key for session management

@app.route('/')
def hello_world():
    return 'Hello World'

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if(user_collection.find_one({"email": data['email']})):
        return "User already exists", 400
    # encrypt the password
    password = data['password']
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    data['password'] = hashed_password
    user_collection.insert_one(data)
    return "User Created!"

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = user_collection.find_one({"email": data['email']})
    if not user:
        return "User not found", 404
    # encrypt the password
    password = data['password']
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    if user['password'] != hashed_password:
        return "Invalid Password", 401
    session['user'] = user
    session['user_id'] = str(user['_id'])
    return "Logged In!"

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    session.pop('user_id', None)
    return "Logged Out!"

@app.route('/get_user_bots', methods=['GET'])
def get_user_bots():
    if 'user' not in session:
        return "Please log in", 401
    user_id = session['user_id']
    bots = list(bot_collection.find({"user_id": user_id}))
    return jsonify(bots)

    
@app.route('/create_bot', methods=['POST'])
def create_bot_endpoint():
    if 'user' not in session:
        return "Please log in", 401

    data = request.get_json()
    data['user_id'] = session['user_id']

    # Insert data into MongoDB 
    bot = bot_collection.insert_one(data)

    return str(bot.inserted_id)

@app.route('/update_bot', methods=['PATCH'])
def update_bot_endpoint():
    if 'user' not in session:
        return "Please log in", 401

    data = request.get_json()
    bot_id = data.pop('_id')

    # Check if the user is the owner of the bot
    bot = bot_collection.find_one({"_id": ObjectId(bot_id), "user_id": session['user_id']})
    if not bot:
        return "You are not authorized to update this bot", 403

    # Update the bot with given id
    bot_collection.update_one({"_id": ObjectId(bot_id)}, {"$set": data})

    return "Bot Updated!"


@app.route('/get_user_conversations', methods=['GET'])
def get_user_conversations():
    if 'user' not in session:
        return "Please log in", 401
    user_id = session['user_id']
    conversations = list(conversation_collection.find({"user_id": user_id}))
    return jsonify(conversations)

@app.route('/create_conversation', methods=['POST'])
def create_conversation_endpoint():
    if 'user' not in session:
        return "Please log in", 401

    data = request.get_json()
    data['user_id'] = session['user_id']
    data['history'] = []

    # Insert data into MongoDB
    conv = conversation_collection.insert_one(data)

    return str(conv.inserted_id)
@app.route('/update_conversation', methods=['PATCH'])
def update_conversation_endpoint():
    if 'user' not in session:
        return "Please log in", 401

    data = request.get_json()
    conversation_id = data.pop('_id')

    # Check if the user is the owner of the conversation
    conversation = conversation_collection.find_one({"_id": ObjectId(conversation_id), "user_id": session['user_id']})
    if not conversation:
        return "You are not authorized to update this conversation", 403

    # Update the conversation with given id
    conversation_collection.update_one({"_id": ObjectId(conversation_id)}, {"$set": data})

    return "Conversation Updated!"

@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.get_json()
    conversation_id, user_message = data['conversation_id'], data['user_message']
    def generate_responses(conversation_id, user_message):
        
        conversation = conversation_collection.find_one({"_id": ObjectId(conversation_id)})
        if not conversation:
            yield json.dumps({"error": "Conversation not found"}) + "\n"
            return
        
        temp_history = conversation['history']
        temp_history.append({"role": "user", "content": user_message})
        # print(temp_history)
        # responses = []

        bots = list(bot_collection.find({"_id": {"$in": [ObjectId(bot_id) for bot_id in conversation['bots']]}}))

        # for bot in bots:
        #     print(bot)
        for i in range(len(bots)):
            bot_response = generate_bot_response(bots[i], bots[:i]+bots[i+1:], temp_history,conversation['scenario'])
            temp_history.append({"role": "user", "content": f'{bots[i]["name"]}: {bot_response}'})
            # responses.append(f"{bots[i]['name']}: {bot_response}")
            r = f"{bots[i]['name']}: {bot_response}"
            yield f"data: {json.dumps(r)}\n\n"

        # Update the conversation history in the database
        conversation_collection.update_one({"_id": ObjectId(conversation_id)}, {"$set": {"history": temp_history}})

    # print(temp_history)
    return Response(generate_responses(conversation_id, user_message), content_type='text/event-stream')

def generate_bot_response(bot, other_bots, conversation_history, conversation_scenario):
    prompt = generate_conversation_prompt(bot, other_bots, conversation_scenario)
    # print(prompt)
    conversation_history = deque(conversation_history)
    conversation_history.appendleft({ "role": 'system', "content": prompt })
    conversation_history = list(conversation_history)
    completion = portkey.chat.completions.create(
        messages = conversation_history,
        model = bot['model_name']
    )
    print(completion.choices[0].message.content)
    return completion.choices[0].message.content

    # GEMINI
    # model = genai.GenerativeModel(
    #     model_name=bot['model_name'],
    #     safety_settings=gemini_safety_settings,
    #     generation_config=gemini_generation_config,
    #     system_instruction=prompt
    # )
    # response = model.generate_content(conversation_history)
    # print(response)
    # return response.text

# Main driver function
if __name__ == '__main__':
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)
    # Run() method of Flask class runs the application
    # on the local development server.
    app.run()
    # Send a ping to confirm a successful connection
    

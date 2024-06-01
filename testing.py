from flask import Flask, request, jsonify, session
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
uri = "mongodb+srv://uditj:Udit%406129@cluster0.ytkma3f.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))


app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello World'

@app.route('/create_bot', methods=['POST'])
def create_bot_endpoint():
    # if 'user' not in session:
    #     return "Please log in", 401

    data = request.get_json()
    print(data) # format of data: {'name': 'bot_name', 'description': 'bot_description',etc...}

    # data.user_id = session['user_id']

    # Insert data into MongoDB 
    # collection.insert_one(data) 

    return "Bot Created!"

@app.route('/update_bot', methods=['PATCH'])
def update_bot_endpoint():
    # update the bot with given id
    
    return "Bot Updated!"

@app.route('/create_conversation', methods=['POST'])
def create_conversation_endpoint():
    # if 'user' not in session:
    #     return "Please log in", 401

    data = request.get_json()
    # data.user_id = session['user_id']
    # data.history = []
    print(data)

    return "Conversation Created!"

@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.get_json()
    conversation_id, user_message = data['conversation_id'], data['user_message']
    # conversation = db.conversations.find_one({"_id": ObjectId(conversation_id)})
    
    temp_history = conversation['history']

    temp_history.append({"role":"user","message":user_message})

    responses = []

    bots = db.bots.find({"_id": {"$in": conversation['bot_ids']}})
    for bot in bots:
        bot_response = generate_bot_response(bot, user_message,temp_history)

        temp_history.append({"role":"user","message":f'{bot["name"]}: {bot_response}'})

        responses.append(f"{bot['name']}: {bot_response}")

    # update the conversation history in the database
    # db.conversations.update_one({"_id": ObjectId(conversation_id)}, {"$set": {"history": temp_history}})
    
    return responses

def generate_bot_response(bot, user_message,conversation_history):
    model = genai.GenerativeModel(
        model_name=bot['model_name'],
        # safety_settings=safety_settings,
        # generation_config=generation_config,
        system_instruction=bot['system_instruction']
    )
    response = model.generate_content(conversation_history)
    return response.text


# main driver function
if __name__ == '__main__':

    # run() method of Flask class runs the application 
    # on the local development server.
    app.run()
    # Send a ping to confirm a successful connection
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)
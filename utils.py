from prompt_templates import chat_prompt_template, conversation_prompt_template

def generate_chat_prompt(bot):
    variables = ["name", "personality", "description", "scenario"]
    prompt = chat_prompt_template
    for var in variables:
        prompt = prompt.replace(f'${var.upper()}', bot[var])
    return prompt

def generate_conversation_prompt(bot, other_bots, conversation_scenario):
    variables = ["name", "personality", "description"]
    prompt = conversation_prompt_template
    for var in variables:
        prompt = prompt.replace(f'${var.upper()}', bot[var])
    prompt = prompt.replace("$SCENARIO", conversation_scenario)
    prompt = prompt.replace("$OTHER_CHARACTERS", ", ".join([other_bot["name"] + " : " + other_bot["personality"] +" person"for other_bot in other_bots]))
    return prompt

def initialize_model(bot):
    prompt = generate_prompt(
        bot_name=bot['name'],
        character_description=bot['description'],
        other_characters=[other_bot['name'] for other_bot in active_bots.values() if other_bot['_id'] != bot['_id']],
        conversation_history=""
    )
    model = genai.GenerativeModel(
        model_name=bot['model_name'],
        safety_settings=safety_settings,
        generation_config=generation_config,
        system_instruction=prompt
    )
    return model
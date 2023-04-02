import json
import requests
from typing import Optional
from utils import create_logger
import time
from os import environ
from db_manager import DBManager

logger = create_logger(__file__)
URL = f"https://api.telegram.org/bot{environ.get('CREAMET_TELEGRAM_TOKEN')}"


def get_request(url: str) -> Optional[str]:
    try:
        response = requests.get(url)
        return response.content.decode("utf8")
    except (requests.exceptions.RequestException, ValueError) as e:
        logger.error(e)
        return None


def json_from_get_request(url: str) -> dict:
    response = get_request(url)
    while response is None:
        time.sleep(float(environ.get('CREMAET_API_ERROR_SLEEP', 2)))
        response = get_request(url)
    return json.loads(response)


def get_updates(offset: Optional[int] = None) -> dict:
    """
    Ask the telegram server for the most recent updates, offset parameter tells the server
    what is the last message that the bot download in order to ignore the previous ones
    """
    # TODO - incorporate mechanism to deal with possible telegram issues
    url = URL + "/getUpdates"
    if offset:
        url = f'{url}?offset={offset}'
    return json_from_get_request(url)


def get_user_field_data(update_json: dict, field: str) -> str | int | None:
    # A generic version of the filter method to obtain the chat id, but it allows to pick any field
    if 'edited_message' in update_json and 'text' in update_json['edited_message']:
        return update_json.get('edited_message').get('chat').get(field)

    elif 'callback_query' in update_json:
        return update_json.get('callback_query').get('from').get(field)

    else:
        return update_json.get("message").get("chat").get(field)


def filter_update(update_json: dict):
    if 'edited_message' in update_json:
        if 'text' in update_json['edited_message']:
            return update_json["edited_message"]["text"].strip(), update_json['edited_message']['message_id']
        else:
            # return none if it's a message without text
            return None, update_json['message']['message_id']

    elif 'callback_query' in update_json:
        # data is the text sent by the callback as a msg
        return update_json['callback_query']['data'], update_json['callback_query']['message']['message_id']

    elif 'message' in update_json:
        if 'text' in update_json['message']:
            return update_json["message"]["text"].strip(), update_json['message']['message_id']
        else:
            # return none if it's a message without text
            return None, update_json['message']['message_id']


if __name__ == '__main__':
    # TODO - load the dialogs
    last_update_id = None
    dbmanager = DBManager()

    # Main loop
    while True:
        updates = get_updates(offset=last_update_id)
        if 'result' not in updates or len(updates['result']) == 0:
            time.sleep(float(environ.get('CREMAET_NO_MESSAGE_TIME', 0.8)))
            continue

        for update in updates['result']:
            text, msg_id = filter_update(update)
            text = text.lower()
            telegram_id = get_user_field_data(update, "id")
            active_user = dbmanager.get_user_by_telegram_id(telegram_id)

            # casos de uso
            if text == 'start' or '/start' in text:
                # Register the user if they are not in the database
                if active_user is None:
                    # TODO - complete the fields
                    active_user = dbmanager.add_user()
                # TODO - send message anf main menu
                pass
            elif text == environ.get('CREMAET_ADMIN_PASSWORD'):
                # TODO - pick the user and change, change the isadmin attribute and save it
                pass



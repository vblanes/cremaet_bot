import json
import requests
from typing import Optional
from utils import create_logger, load_dialogs
import time
from os import environ
from db_manager import DBManager
from db_tables import User, StatusEnum
from urllib.parse import quote_plus
from collections import deque
from datetime import datetime, timedelta

logger = create_logger(__file__)
URL = f"https://api.telegram.org/bot{environ.get('CREAMET_TELEGRAM_TOKEN')}"
dialogs = load_dialogs()


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


def send_message(text2send: str, telegram_recipient: int, reply_markup=None):
    text2send = quote_plus(text2send)
    url = URL + f"sendMessage?text={text2send}&chat_id={telegram_recipient}&parse_mode=Markdown"
    # reply_markup is for a special keyboard
    if reply_markup:
        url += "&reply_markup={}".format(reply_markup)
    return json_from_get_request(url)


def generate_main_keyboard(admin: bool):
    if not admin:
        keyboard = {'inline_keyboard': [
            [{'text': 'Registro', 'callback_data': '/log'},
             {'text': 'Ranking', 'callback_data': '/ranking'}],
            [{'text': 'A qui li toca pagar??', 'callback_data': '/pay'}]
        ]}
    else:
        keyboard = {'inline_keyboard': [
            [{'text': 'Registro', 'callback_data': '/log'},
             {'text': 'Ranking', 'callback_data': '/ranking'}],
            [{'text': '¡Pagado!', 'callback_data': '/paid'},
             {'text': 'Nuevo miembro', 'callback_data': '/member'}],
            [{'text': 'A qui li toca pagar??', 'callback_data': '/whopays'}]
        ]}
    return keyboard


def main_menu(user: User):
    # Macro to send a Telegram user to the main menu
    db = DBManager()
    db.change_user_status(user, StatusEnum.MAIN_MENU)
    # Generate the keyboard option
    keyboard = generate_main_keyboard(user.is_admin)
    send_message(dialogs['main_manu'], user.telegram_id, json.dumps(keyboard))


def rotatory_algorithm() -> deque:
    # Use a stack to determine the turn
    # Apply the algorithm!
    stack = deque()
    # first, get all the participants. This dict is also a way to keep track
    participants_dict = {p.participant_id: p.display_name for p in dbmanager.get_all_participants()}
    # Pick all events
    for event in dbmanager.get_all_events():
        # All participants are already included
        if not participants_dict:
            break
        # It is a holiday or whatever, skip this iteration
        if event.not_available:
            continue
        participant_id = event.participant
        if participant_id in participants_dict:
            # Add the name to the stack
            stack.appendleft(participants_dict.get(participant_id))
            # Also, remove this from the dict
            participants_dict.pop(participant_id)
    # Now, check if there is some left in the dict
    # They have no registries yet - Add in any order
    if participants_dict:
        for name in participants_dict.values():
            stack.appendleft(name)
    return stack


def next_event_day() -> str:
    # This is a specific function of the cremaet bot
    # returns the date of the next friday as a str
    db = DBManager()
    last_event = db.get_last_n_events(1)[0]
    return_date: datetime = last_event.date.copy()
    if is_friday(return_date):
        return_date += timedelta(days=7)
    else:
        return_date += timedelta(days=1)
        while not is_friday(return_date):
            return_date += timedelta(days=1)
    return return_date.strftime('%d/%m/%Y')


def is_friday(date: datetime):
    # Checkme - changing the name of the func and the number
    # This function could be used in other settings!
    return date.weekday() != 4


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
                    # Checkme - is this the appropiate function?
                    first_name = get_user_field_data('first_name')
                    last_name = get_user_field_data('last_name')
                    active_user = dbmanager.add_user()
                main_menu(active_user)
            elif text == environ.get('CREMAET_ADMIN_PASSWORD'):
                dbmanager.promote_to_admin(active_user)
                send_message(dialogs.get('promoted_admin'), active_user.telegram_id)
                main_menu(active_user)
            elif text.startswith('/log'):
                tokens = text.split(' ')
                #checkme this could be parametrized with environ
                n_registries = 5
                # check for manual params
                if len(tokens) > 1:
                    if tokens[1].isnumeric():
                        n_registries = int(tokens[1])
                # sanity check - only positive values
                if n_registries <= 0:
                    n_registries = 5
                last_events = dbmanager.get_last_n_events(n_registries)
                # checkme - table type message
                message = ''
                for registry in last_events:
                    participant_name = dbmanager.get_participant_by_id(registry.participant)
                    if participant_name is None:
                        # TODO - this can be parametrized!
                        participant_name = 'Festa!'
                    message += f'{registry.event_id} \t {participant_name} \t {registry.date} \n'
                    send_message(message, active_user)
                    main_menu(active_user)

            elif text.startswith('/ranking'):
                # Pick the different participants
                participants = dbmanager.get_all_participants
                ranking = dict()
                for participant in participants:
                    ranking[participant.display_name] = len(dbmanager.get_events_by_participant(participant))
                # checkme - table type message
                # prepare the message
                message = ''
                for k, v in sorted(ranking.items(), key=lambda item: item[1]):
                    message += f'{k} \t {v} \n'

            elif text.startswith('/whopays'):
                ordered_turns = rotatory_algorithm()
                next_date = next_event_day()
                message = f'{ordered_turns[0]} - {next_date}'
                send_message(message, active_user)
                main_menu(active_user)

            elif text.startswith('/event'):
                pass

            elif text.startswith('/member'):
                # check the tokens, advance user may use params options
                pass

            # TODO - los deletes
            else:
                pass



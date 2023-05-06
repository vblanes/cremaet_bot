import json
import requests
from typing import Optional, Union
from utils import create_logger, load_dialogs
import time
from os import environ
from db_manager import DBManager
from db_tables import User, StatusEnum
from urllib.parse import quote_plus
from collections import deque
from datetime import datetime, timedelta
from icecream import ic
import pandas as pd
from copy import copy

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


def post_request(url: str, files, data) -> Optional[str]:
    try:
        response = requests.post(url=url, files=files, data=data)
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


def get_user_field_data(update_json: dict, field: str) -> Optional[Union[str, int]]:
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


def send_image(img_path: str, user_chat_id: int, caption: Optional[str] = None) -> Optional[requests.Response]:
    url = URL + "/sendPhoto"
    # TODO - load the img as bytes from the folder
    with open(img_path, 'rb') as img_reader:
        img = img_reader.read()
    files = {'photo': img}
    data = {'chat_id': user_chat_id}
    if caption:
        data['caption'] = caption
    response = None
    while response is None:
        time.sleep(float(environ.get('CREMAET_API_ERROR_SLEEP', 2)))
        response = post_request(url, files, data)
    return response


def send_message(text2send: str, telegram_recipient: int, reply_markup=None):
    text2send = quote_plus(text2send)
    url = URL + f"/sendMessage?text={text2send}&chat_id={telegram_recipient}&parse_mode=Markdown"
    # reply_markup is for a special keyboard
    if reply_markup:
        url += f"&reply_markup={reply_markup}"
    return json_from_get_request(url)


def generate_main_keyboard(admin: bool):
    if not admin:
        keyboard = {'inline_keyboard': [
            [{'text': 'Registro', 'callback_data': '/log'},
             {'text': 'Ranking', 'callback_data': '/ranking'}],
            [{'text': 'A qui li toca pagar??', 'callback_data': '/whopays'}]
        ]}
    else:
        keyboard = {'inline_keyboard': [
            [{'text': 'Registro', 'callback_data': '/log'},
             {'text': 'Ranking', 'callback_data': '/ranking'}],
            [{'text': '¡Pagado!', 'callback_data': '/event'},
             {'text': 'Nuevo miembro', 'callback_data': '/member'}],
            [{'text': 'A qui li toca pagar??', 'callback_data': '/whopays'},
             {'text': 'Añadir dia libre', 'callback_data': '/holiday'}]
        ]}
    return keyboard


def main_menu(user: User):
    # Macro to send a Telegram user to the main menu
    db = DBManager()
    db.change_user_status(user, StatusEnum.MAIN_MENU)
    # Generate the keyboard option
    keyboard = generate_main_keyboard(user.is_admin)
    ic(send_image('images/cremaetin.jpg', user.telegram_id))
    send_message(dialogs['main_menu'], user.telegram_id, json.dumps(keyboard))


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
    return_date: datetime = copy(last_event.date)
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
    return date.weekday() == 4


def not_command_response(user: User):
    pass


def get_last_update_id(server_updates: dict) -> int:
    return max([int(el.get('update_id')) for el in server_updates.get('result')])


def populate_database_from_file():
    df = pd.read_csv('backup.csv', sep=';')
    common_init_date = None
    participant_set = set()
    db = DBManager()
    for row in df.itertuples():
        participant_display = row.participant.strip()
        payment_date = datetime.strptime(row.date, '%d/%m/%Y')

        # This is just for the first time
        if common_init_date is None:
            common_init_date = payment_date

        if participant_display not in participant_set:
            db.add_participant(participant_display, common_init_date)
            participant_set.add(participant_display)

        participant_object = db.get_participant_by_display_name(participant_display)
        db.add_event(participant_object, payment_date)


def display_log(user: User, tokens_command: list, n_registries: int = 5) -> None:
    db = DBManager()
    # check for manual params
    if len(tokens_command) > 1:
        if tokens_command[1].isnumeric():
            n_registries = int(tokens_command[1])
    # sanity check - only positive values
    if n_registries <= 0:
        n_registries = 5
    last_events = db.get_last_n_events(n_registries)
    # checkme - table type message
    message_to_user = ''
    for registry in last_events:
        participant_name = db.get_participant_by_id(registry.participant)
        if participant_name is None:
            participant_name = dialogs.get('log_holiday_display')
        else:
            participant_name = participant_name.display_name
        # TODO el formato es terrible
        message_to_user += f'{registry.event_id} \t {participant_name} \t\t\t {registry.date.date()} \n'
    if not message_to_user:
        message_to_user = dialogs.get('no_log')
    send_message(message_to_user, user.telegram_id)
    main_menu(user)


def display_ranking(user: User) -> None:
    db = DBManager()
    # Pick the different participants
    participants = db.get_all_participants()
    ranking = dict()
    for participant_ in participants:
        ranking[participant_.display_name] = len(db.get_events_by_participant(participant_))
    # checkme - table type message
    # prepare the message
    message_to_user = ''
    for k, v in sorted(ranking.items(), key=lambda item: item[1]):
        message_to_user += f'{k} \t {v} \n'
    # Sanity check
    if not message_to_user:
        message_to_user = dialogs.get('no_ranking')
    send_message(message_to_user, user.telegram_id)
    main_menu(user)


def display_who_pays(user: User, n_events: int = 1) -> None:
    turns = rotatory_algorithm()
    next_date = next_event_day()
    # sanity check to avoid injection of negative values
    if n_events < 1:
        n_events = 1

    message_to_user = f'Li toca pagar a: {turns[0]} - {next_date}'
    if n_events > 1:
        message_to_user += '\n Después li tocaría a:\n'
        n_iters = max(n_events, len(turns))
        for it in range(1, n_iters):
            message_to_user += f'{turns[it]}\n'

    send_message(message_to_user, user.telegram_id)
    main_menu(user)


def add_event(user: User, tokens_command: list) -> None:
    # TODO - Add the option to add an ammount at the end of the command
    # Advanced use of the bot
    if len(tokens_command) >= 3:
        # second token is the participant
        participant_str = tokens_command[1]
        participant = dbmanager.get_participant_by_display_name(participant_str)
        if participant is None:
            send_message(dialogs.get('participant_not_found'), user.telegram_id)
            return
        # check the validity of the date
        try:
            date_event = datetime.strptime(tokens_command[2], '%d/%m/%Y')
        except ValueError:
            send_message(dialogs.get('date_bad_format'), user.telegram_id)
            return
        # TODO - maybe check if it's friday??
        # If the method has not reached any continue here, we have a correct date and participant
        res = dbmanager.add_event(participant, date_event)
        message_to_user = dialogs.get('event_added_ok') if res else dialogs.get('event_added_error')
        send_message(message_to_user, user.telegram_id)
        main_menu(user)

    # Bot guided use
    else:
        dbmanager.change_user_status(user, StatusEnum.ADDING_EVENT)
        # calculate the next friday and just ask for the participant name
        next_day = next_event_day()
        message_to_user = dialogs.get('add_event').replace('%$%', next_day)
        send_message(message_to_user, user.telegram_id)


def add_holidays(user: User, tokens_command: list):
    # advanced mode
    if len(tokens_command) == 2:
        try:
            date_holiday = datetime.strptime(tokens_command[1], '%d/%m/%Y')
        except ValueError:
            send_message(dialogs.get('date_bad_format'), user.telegram_id)
            return
        event = dbmanager.add_event(None, date_holiday, True)
        message = dialogs.get('holiday_added_ok') if event else dialogs.get('holiday_added_error')
        ic(message)
        send_message(message, user.telegram_id)
        main_menu(user)
    else:
        send_message(dialogs.get('add_holiday'), user.telegram_id)
        return


if __name__ == '__main__':
    logger.warning('Starting bot')
    # TODO - load the dialogs
    last_update_id = None
    dbmanager = DBManager()
    logger.warning('Entering main loop')
    # Main loop
    while True:
        try:
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
                ic(text)
                if text == 'start' or '/start' in text:
                    # Register the user if they are not in the database
                    if active_user is None:
                        # Checkme - is this the appropiate function?
                        first_name = get_user_field_data(update, 'first_name')
                        last_name = get_user_field_data(update, 'last_name')
                        active_user = dbmanager.add_user(telegram_id, first_name, last_name)

                    main_menu(active_user)
                elif text == environ.get('CREMAET_ADMIN_PASSWORD'):
                    dbmanager.promote_to_admin(active_user)
                    send_message(dialogs.get('promoted_admin'), active_user.telegram_id)
                    main_menu(active_user)
                elif text.startswith('/log'):
                    tokens = text.split(' ')
                    display_log(user=active_user, tokens_command=tokens)

                elif text.startswith('/ranking'):
                    display_ranking(user=active_user)

                elif text.startswith('/whopays'):
                    tokens = text.split(' ')
                    argument = 1
                    if len(tokens) > 1 and tokens[1].isnumeric():
                        argument = int(tokens[1])
                    display_who_pays(user=active_user, n_events=argument)

                elif text.startswith('/event'):
                    tokens = text.split(' ')
                    add_event(user=active_user, tokens_command=tokens)

                elif text.startswith('/participant'):
                    # create one participant
                    tokens = text.split(' ')
                    # Advanced participant creation
                    if len(tokens) >= 2:
                        participant_display_name = tokens[1].strip()
                        date_join = datetime.today()
                        # In case the date is provided
                        if len(tokens) == 3:
                            try:
                                date_join = datetime.strptime(tokens[2], '%d/%m/%Y')
                            except ValueError:
                                send_message(dialogs.get('date_bad_format'), active_user.telegram_id)
                                continue
                        # create the participant
                        dbmanager.add_participant(participant_display_name, date_join)
                        # TODO - send okay message
                        main_menu(active_user)
                    # TODO - Manual way
                    else:
                        pass
                elif text.startswith('/holiday'):
                    tokens = text.split(' ')


                # TODO - los deletes

                elif text == 'load_backup':
                    populate_database_from_file()
                else:
                    not_command_response(active_user)

                last_update_id = get_last_update_id(updates) + 1
                time.sleep(float(environ.get('CONSULTING_TIME', 0.4)))
        except Exception as e:
            logger.error(e)
            time.sleep(float(environ.get('CREMAET_API_ERROR_SLEEP', 0.8)))
            continue

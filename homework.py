import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot, apihelper


from exceptions import NoTokenError, ResponseError, ResponseStatusError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TKN')
TELEGRAM_TOKEN = os.getenv('TG_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TGR_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS: dict[str, str] = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
file_handler = logging.FileHandler(
    filename='main.log', mode='w', encoding='utf-8')
logger.addHandler(file_handler)
formatter = logging.Formatter(
    '%(asctime)s %(levelname)s %(funcName)s %(lineno)d %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN: Токен доступа к Практикум.Домашка': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN: Токен доступа к телеграмм боту': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID: ID получателя сообщений': TELEGRAM_CHAT_ID}
    failed_list = []
    for description, token in tokens.items():
        if token is None:
            failed_list.append(description)
    if failed_list:
        failed_str = ', '.join(failed for failed in failed_list)
        logger.critical(
            'Ошибка при проверке наличия токенов. '
            'Отсутствуют следующие токены: '
            f'{failed_str}. '
            'Работа программы прекращена.')
        raise NoTokenError(
            'Отсутствуют необходимые токены: '
            f'{failed_str}. '
        )


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        logger.debug('Начало отправки сообщения.')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID,
                         text=message)
        logger.debug('Сообщение отправлено.')
        return True
    except apihelper.ApiException as error:
        logger.error(f'Ошибка запроса к Telegram API. {error}')
        return False
    except Exception as error:
        logger.error(f'Сообщение "{message}" не было отправлено. {error}')
        return False


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    request_settings = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}}
    try:
        logger.debug(f'Делаем запрос к API: {request_settings}')
        response = requests.get(**request_settings)
    except requests.RequestException as error:
        raise ResponseError(
            'Во время получения ответа сервера произошла ошибка'
            f'{error}')

    if response.status_code != HTTPStatus.OK:
        raise ResponseStatusError(
            'Ошибка в ответе сервера. '
            f'Сервер вернул статус: {response.status_code}'
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Тип ответа API домашки должен быть dict.'
                        f'Получен тип {type(response)}.')
    try:
        homeworks = response['homeworks']
    except KeyError:
        raise KeyError('В ответе API домашки нет ключа `homeworks.')
    if not isinstance(homeworks, list):
        raise TypeError(
            'Список домашних работ должен быть типа list'
            f'Получен {type(homeworks)}')
    return homeworks


def parse_status(homework: dict[str, str]) -> str:
    """Извлекает статус домашней работы."""
    try:
        homework_name = homework['homework_name']
        status = homework['status']
    except KeyError as error:
        raise KeyError(
            f'{error}. В ответе API домашки нет необходимого ключа.'
        )
    try:
        verdict = HOMEWORK_VERDICTS[status]
    except KeyError as error:
        raise KeyError(
            f'Неожиданный статус домашней работы: {status}. {error}'
        )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def unix_to_dt(timestamp):
    """Преобразует UNIX в местное время."""
    time_now = time.strftime(
        '%H:%M %d-%m-%Y',
        time.localtime(timestamp)
    )
    return time_now


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            time_now = unix_to_dt(timestamp)
            if not homeworks:
                logger.debug(f'Статус домашки не менялся с {time_now}')
            else:
                message = parse_status(homeworks[0])
                if send_message(bot, message):
                    timestamp = response.get('current_date', timestamp)
                    time_now = unix_to_dt(timestamp)
                logger.debug(f'Следущая проверка стартует с {time_now}')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if last_message != message:
                send_message(bot, message)
                last_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

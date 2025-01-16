import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot

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

"""logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s',
    level=logging.DEBUG,
    filename='main.log',
    filemode='w'
)"""

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=None)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s %(levelname)s %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    tokens_is_valid = all(tokens)

    return tokens_is_valid


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID,
                         text=message)
        logger.debug('Сообщение отправлено.')
    except Exception as error:
        logger.error(f'Сообщение "{message}" не было отправлено. {error}')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    try:
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp})
        response.raise_for_status()
        if response.status_code != HTTPStatus.OK:
            raise Exception('Ошибка в ответе сервера:')
        response = response.json()
        return response
    except Exception as error:
        raise Exception(f'Во время получения ответа сервера произошла ошибка'
                        f'{error}')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logger.error('Ответ API домашки должен быть словарем.')
        raise TypeError('Ответ API домашки должен быть словарем.')
    homeworks = response.get('homeworks')
    if homeworks is None:
        raise KeyError('В ответе API домашки нет ключа `homeworks.')
    if not isinstance(homeworks, list):
        raise TypeError('Список домашних работ должен быть списком')
    return homeworks


def parse_status(homework: dict[str, str]) -> str:
    """Извлекает статус домашней работы."""
    try:
        homework_name = homework['homework_name']
    except Exception as error:
        logger.error(f'{error}. API домашки нет ключа "homework_name".')

    status = homework.get('status')

    try:
        verdict = HOMEWORK_VERDICTS[str(status)]
    except Exception as error:
        logger.error(f'Неожиданный статус домашней работы: {status}. {error}')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Ошибка при проверке наличия токенов')
        sys.exit()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            valid_response = check_response(response)
            if len(valid_response) == 0:
                logger.debug('Статус домашки не изменился')
            else:
                message = parse_status(valid_response[0])
                send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            ...
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

import pickle
import time
import threading

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, ConversationHandler, Filters

from server import DmServer
from formatting import DmFormat, QUESTIONS_PER_ROUND

ERROR_TITLE_KEY = 'popup_title'
ERROR_MESSAGE_KEY = 'popup_mess'
LOGGED_IN_KEY = 'logged_in'
PLAYER_ACTION_BUTTONS = ReplyKeyboardMarkup([['Играть!'], ['Добавить в друзья']], one_time_keyboard=True,
                                            resize_keyboard=True)
GET_GAME_ID, GET_GAME_ACTION, P1Q1, P1Q2, P1Q3, P2Q1, P2Q2, P2Q3, GET_NEXT_CATEGORY, GIVE_UP_CONFIRM = range(
    10)  # /list
GET_LOGIN, GET_PASSWORD, GET_EMAIL = range(3)  # /auth and /register
GET_OPPONENT_NAME, GET_FIND_ACTION = range(2)  # /find


def start(bot, update):
    update.message.reply_text('Я бот игры "Борьба умов". Получите список доступных команд, набрав /help',
                              reply_markup=ReplyKeyboardRemove())


def help(bot, update):
    update.message.reply_text('''Список команд:
/start - запуск бота
/register - создать новый аккаунт
/auth - авторизация
/list - показать список игр
/find <логин> - поиск пользователя <логин>
/random - начать игру со случайным игроком
/reset - выйти в главное меню
/help - помощь''', reply_markup=ReplyKeyboardRemove())


def reset(bot, update):
    update.message.reply_text('Вы вернулись в главное меню!')
    help(bot, update)


def register(bot, update):
    update.message.reply_text('Введите логин:', reply_markup=ReplyKeyboardRemove())
    return GET_LOGIN


def get_login_register(bot, update, user_data):
    user_data['login'] = update.message.text
    update.message.reply_text('Введите пароль:')
    return GET_PASSWORD


def get_password_register(bot, update, user_data):
    user_data['password'] = update.message.text
    update.message.reply_text('Введите email или введите 0:')
    return GET_EMAIL


def get_email_register(bot, update, user_data):
    user_data['email'] = update.message.text
    server = DmServer()
    response = server.create_user(user_data['login'], user_data['password'],
                                  user_data['email'] if user_data['email'] != '0' else None)
    if ERROR_MESSAGE_KEY in response:
        update.message.reply_text(response[ERROR_MESSAGE_KEY])
    if LOGGED_IN_KEY in response and response[LOGGED_IN_KEY]:
        user_data['session'] = pickle.dumps(server)
        update.message.reply_text('Успешно!')
    return ConversationHandler.END


def auth(bot, update):
    update.message.reply_text('Введите логин:', reply_markup=ReplyKeyboardRemove())
    return GET_LOGIN


def get_login_auth(bot, update, user_data):
    user_data['login'] = update.message.text
    update.message.reply_text('Введите пароль:')
    return GET_PASSWORD


def get_password_auth(bot, update, user_data):
    user_data['password'] = update.message.text
    server = DmServer()
    response = server.login(user_data['login'], user_data['password'])
    if ERROR_MESSAGE_KEY in response:
        update.message.reply_text(response[ERROR_MESSAGE_KEY])
    if LOGGED_IN_KEY in response and response[LOGGED_IN_KEY]:
        user_data['session'] = pickle.dumps(server)
        update.message.reply_text('Успешно!')
    return ConversationHandler.END


def find(bot, update, args, user_data):
    if 'session' not in user_data or not user_data['session']:
        update.message.reply_text('Необходима авторизация!', reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    if args:
        user_data['opponent'] = args[0]
        return find_user(bot, update, user_data)
    update.message.reply_text('Введите логин соперника:', reply_markup=ReplyKeyboardRemove())
    return GET_OPPONENT_NAME


def get_opponent_name(bot, update, user_data):
    user_data['opponent'] = update.message.text
    return find_user(bot, update, user_data)


def find_user(bot, update, user_data):
    session = pickle.loads(user_data['session'])
    response = session.find_user(user_data['opponent'])
    if ERROR_MESSAGE_KEY in response:
        update.message.reply_text(response[ERROR_MESSAGE_KEY], reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    else:
        update.message.reply_text(
            'Пользлватель {} найден! Какое действие вы хотите совершить?'.format(user_data['opponent']),
            reply_markup=PLAYER_ACTION_BUTTONS)
        user_data['opponent_id'] = response['u']['user_id']
        return GET_FIND_ACTION


def user_action(bot, update, user_data):
    answer = update.message.text
    session = pickle.loads(user_data['session'])
    if answer == 'Играть!':
        response = session.create_game(user_data['opponent_id'])
    elif answer == 'Добавить в друзья':
        update.message.reply_text('Данная функция находится в разработке', reply_markup=PLAYER_ACTION_BUTTONS)
        return GET_FIND_ACTION
    else:
        update.message.reply_text('Выберите корректное действие!', reply_markup=PLAYER_ACTION_BUTTONS)
        return GET_FIND_ACTION
    if ERROR_MESSAGE_KEY in response:
        update.message.reply_text(response[ERROR_MESSAGE_KEY], reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text('Успешно!', reply_markup=ReplyKeyboardRemove())
    del user_data['opponent_id']
    del user_data['opponent']
    return ConversationHandler.END


def start_random_game(bot, update, user_data):
    if 'session' not in user_data or not user_data['session']:
        update.message.reply_text('Необходима авторизация!', reply_markup=ReplyKeyboardRemove())
    else:
        session = pickle.loads(user_data['session'])
        response = session.start_random_game()
        if ERROR_MESSAGE_KEY in response:
            update.message.reply_text(response[ERROR_MESSAGE_KEY], reply_markup=ReplyKeyboardRemove())
        else:
            update.message.reply_text('Успешно!', reply_markup=ReplyKeyboardRemove())


def load_games_list(bot, update, user_data):
    def make_text(games, keyboard):
        text = ''
        for game in games:
            hours = game['elapsed_min'] // 60
            game['time'] = '%s час' % hours if hours else '%s мин' % game['elapsed_min']
            game['score'] = '%s - %s' % (
                game['your_answers'].count(0),
                game['opponent_answers'][:-QUESTIONS_PER_ROUND].count(0) if game['your_turn'] else game[
                    'opponent_answers'].count(0))

            if game['state'] == 6:
                game['score'] += ' (Время вышло)'

            text += 'Оппонент: {}\nСчёт: {}\nАктивность: {}\n\n'.format(game['opponent']['name'], game['score'],
                                                                        game['time'])
            keyboard.append(["{} ({}) | {}".format(game['opponent']['name'], game['score'], game['game_id'])])
        return text.strip()

    if 'session' not in user_data or not user_data['session']:
        update.message.reply_text('Необходима авторизация!', reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    session = pickle.loads(user_data['session'])
    response = session.reload_games_list()
    if ERROR_MESSAGE_KEY in response:
        update.message.reply_text(response[ERROR_MESSAGE_KEY], reply_markup=ReplyKeyboardRemove())
    if 'user' in response:
        games = response['user']['games']
        user_data['games'] = games
        # Waiting for your turn
        active_games = sorted(list(filter(
            lambda g: g['state'] in [0, 1, 10] and g['your_turn'], games)), key=lambda t: t['elapsed_min'])
        # Waiting for opponent
        waiting_games = sorted(list(filter(lambda g: g['state'] in [0, 1, 10] and not g['your_turn'], games)),
                               key=lambda t: t['elapsed_min'])
        # Finished Games
        finished_games = sorted(list(filter(lambda g: g['state'] not in [0, 1, 10], games)),
                                key=lambda t: t['elapsed_min'])
        keyboard = []
        if not any([finished_games, active_games, waiting_games]):
            update.message.reply_text('Список игр пуст', reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if active_games:
            keyboard.append(['ℹ️  Активные игры (ваш ход)  ℹ️'])
            update.message.reply_text('Активные игры (ваш ход):\n' + make_text(active_games, keyboard))
        if waiting_games:
            keyboard.append(['ℹ️  Ожидается ход соперника  ℹ️'])
            update.message.reply_text('Ожидается ход соперника:\n' + make_text(waiting_games, keyboard))
        if finished_games:
            keyboard.append(['ℹ️  Завершённые игры  ℹ️'])
            update.message.reply_text('Завершённые игры:\n' + make_text(finished_games, keyboard))
        keyboard.append('Вернуться в главное меню ↩')
        user_data['keyboard'] = keyboard
        update.message.reply_text('Выберите игру:', reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,
                                                                                     resize_keyboard=True))
        return GET_GAME_ID
    else:
        update.message.reply_text('Проблема с получением списка игр!')
        return ConversationHandler.END


def ask_game(bot, update, user_data):
    answer = update.message.text
    if answer.startswith('ℹ️'):
        update.message.reply_text('Данная кнопка не является кликабельной!\nВыберите игру:',
                                  reply_markup=ReplyKeyboardMarkup(user_data['keyboard'], one_time_keyboard=True,
                                                                   resize_keyboard=True))
        return GET_GAME_ID
    elif answer.startswith('Вернуться в главное меню ↩'):
        return ConversationHandler.END
    game_id = answer.split('|')[-1].strip()
    user_data['game_id'] = game_id
    return load_game(bot, update, user_data, game_id)


def load_game(bot, update, user_data, game_id):
    def get_emoji(bool):
        if bool is None:
            return '⚪'  # white circle
        return '✅' if bool else '❌'

    session = pickle.loads(user_data['session'])
    response = session.load_game(game_id)
    if ERROR_MESSAGE_KEY in response:
        update.message.reply_text('Ошибка при загрузке игры!\n' + ERROR_MESSAGE_KEY)
        return ConversationHandler.END
    try:
        game = DmFormat(response).json_to_game()
        user_data['current_game'] = pickle.dumps(game)
    except:
        update.message.reply_text('Ошибка при загрузке игры!')
        return ConversationHandler.END
    text = 'Оппонент: {}\nСчёт: {} - {}\n'.format(game.opponent_name, game.my_score, game.opponent_score)
    # Drawing game table
    for r_num, round_ in enumerate(game.get_table()):
        me, opponent = round_
        for i in range(QUESTIONS_PER_ROUND):
            text += get_emoji(me[i])
        text += ' ' * 7
        if game.state == 1 and r_num + 1 == game.current_round.number:
            text += ' СКРЫТО' if game.is_my_turn else '  ИГРАЕТ'
        else:
            for i in range(QUESTIONS_PER_ROUND):
                text += get_emoji(opponent[i])
        text += '\n'
    if game.is_my_turn is None:
        text += game.result + '\n'
        if game.rating_bonus:
            text += 'Очков рейтига: ' + game.rating_bonus
        GAME_ACTION_BUTTONS = ReplyKeyboardMarkup([['Вернуться к списку игр ↩']],
                                                  one_time_keyboard=True, resize_keyboard=True)
    elif game.is_my_turn:
        GAME_ACTION_BUTTONS = ReplyKeyboardMarkup([['Играть 🎮', 'Сдаться ❗'], ['Вернуться к списку игр ↩']],
                                                  one_time_keyboard=True, resize_keyboard=True)
    else:
        GAME_ACTION_BUTTONS = ReplyKeyboardMarkup([['Синхронизировать 🔄', 'Сдаться ❗'], ['Вернуться к списку игр ↩']],
                                                  one_time_keyboard=True, resize_keyboard=True)
    user_data['keyboard'] = GAME_ACTION_BUTTONS
    update.message.reply_text(text, reply_markup=GAME_ACTION_BUTTONS)
    return GET_GAME_ACTION


def game_menu_action(bot, update, user_data):
    answer = update.message.text
    if answer == 'Играть 🎮':
        del user_data['keyboard']
        try:  # FIXME: DEBUG
            return processing(bot, update, user_data)
        except Exception as exception:
            update.message.reply_text('Кажется что-то пошло не так. Ошибка: {}'.format(exception),
                                      reply_markup=user_data['keyboard'])
    elif answer == 'Синхронизировать 🔄':
        return load_game(bot, update, user_data, user_data['game_id'])
    elif answer == 'Сдаться ❗':
        update.message.reply_text('Вы действительно хотите сдаться?',
                                  reply_markup=ReplyKeyboardMarkup([['Да ✅', 'Нет ❌']], resize_keyboard=True))
        return GIVE_UP_CONFIRM
    elif answer == 'Вернуться к списку игр ↩':
        del user_data['keyboard']
        del user_data['game_id']
        return load_games_list(bot, update, user_data)
    else:
        update.message.reply_text('Выберите корректное действие!', reply_markup=user_data['keyboard'])
        return GET_GAME_ACTION


def give_up_confirm(bot, update, user_data):
    answer = update.message.text
    if answer not in ['Да ✅', 'Нет ❌']:
        update.message.reply_text('Выберите корректный вариант!',
                                  reply_markup=ReplyKeyboardMarkup([['Да ✅', 'Нет ❌']], resize_keyboard=True))
        return GIVE_UP_CONFIRM
    elif answer == 'Да ✅':
        session = pickle.loads(user_data['session'])
        session.give_up(user_data['game_id'])
        update.message.reply_text('Вы сдались!', reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    else:
        return load_game(bot, update, user_data, user_data['game_id'])


def processing(bot, update, user_data):
    game = pickle.loads(user_data['current_game'])
    if game.state == 1:
        # Устанавливаем категорию текущего раунда
        game.current_round.set_category_by_index(game.cat_choices[game.current_round.number - 1])
        user_data['current_game'] = pickle.dumps(game)
        ask_question(bot, update, user_data, 1)
        return P1Q1
    elif game.state in [0, 10]:
        return ask_category(bot, update, user_data)


def ask_question(bot, update, user_data, question):
    game = pickle.loads(user_data['current_game'])
    question = game.current_round.get_questions()[question - 1]
    variants = question.rand_answers
    keyboard = ReplyKeyboardMarkup([[variants[0].text, variants[1].text], [variants[2].text, variants[3].text]],
                                   one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text(question.question_text, reply_markup=keyboard)
    user_data['current_game'] = pickle.dumps(game)


def get_answer(bot, update, user_data, question):
    answer = update.message.text
    game = pickle.loads(user_data['current_game'])
    question = game.current_round.get_questions()[question - 1]
    answer_id = question.get_answer_id_by_string(answer)
    game.my_answers.append(answer_id)
    user_data['current_game'] = pickle.dumps(game)

    text = ''
    variants = question.rand_answers
    for var in variants:
        if var.id == 0:
            emoji = '✅'
        elif var.id == answer_id:
            emoji = '❌'
        else:
            emoji = '⚪'
        text += '{} {}\n'.format(emoji, var.text)
    update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())


def ask_category(bot, update, user_data):
    game = pickle.loads(user_data['current_game'])
    a, b, c = [cat.name for cat in game.current_round.categories_variants]
    update.message.reply_text('Выберите категорию для противника:',
                              reply_markup=ReplyKeyboardMarkup([[a, b], [c]], resize_keyboard=True))
    return GET_NEXT_CATEGORY


def set_category(bot, update, user_data):
    category = update.message.text
    game = pickle.loads(user_data['current_game'])
    if not game.current_round.set_category_by_name(category):
        return ask_category(bot, update, user_data)
    user_data['current_game'] = pickle.dumps(game)
    ask_question(bot, update, user_data, 1)
    return P1Q1 if len(game.opponent_answers) == 0 else P2Q1


def p1q1(bot, update, user_data):
    get_answer(bot, update, user_data, 1)
    ask_question(bot, update, user_data, 2)
    return P1Q2


def p1q2(bot, update, user_data):
    get_answer(bot, update, user_data, 2)
    ask_question(bot, update, user_data, 3)
    return P1Q3


def p1q3(bot, update, user_data):
    get_answer(bot, update, user_data, 3)
    game = pickle.loads(user_data['current_game'])
    if game.current_round.number != 6 and game.state == 1:
        game.current_round = game.get_round_by_index(game.current_round.number)
        user_data['current_game'] = pickle.dumps(game)
        return ask_category(bot, update, user_data)
    else:
        session = pickle.loads(user_data['session'])
        round_end_info = game.round_end()
        session.upload_round_answers(*round_end_info)
        return load_game(bot, update, user_data, user_data['game_id'])


def p2q1(bot, update, user_data):
    get_answer(bot, update, user_data, 1)
    ask_question(bot, update, user_data, 2)
    return P2Q2


def p2q2(bot, update, user_data):
    get_answer(bot, update, user_data, 2)
    ask_question(bot, update, user_data, 3)
    return P2Q3


def p2q3(bot, update, user_data):
    get_answer(bot, update, user_data, 3)
    game = pickle.loads(user_data['current_game'])
    session = pickle.loads(user_data['session'])
    round_end_info = game.round_end()
    session.upload_round_answers(*round_end_info)
    return load_game(bot, update, user_data, user_data['game_id'])


def main(updater):
    def load_data():
        try:
            f = open('userdata', 'rb')
            dp.user_data = pickle.load(f)
            f.close()
        except:
            pass

    def save_data():
        while True:
            try:
                f = open('userdata', 'wb+')
                pickle.dump(dp.user_data, f)
                f.close()
            except Exception:
                pass
            finally:
                time.sleep(60)

    dp = updater.dispatcher

    load_data()
    threading.Thread(target=save_data).start()

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))

    register_conversation = ConversationHandler(
        entry_points=[CommandHandler('register', register)],
        states={
            GET_LOGIN: [MessageHandler(Filters.text, get_login_register, pass_user_data=True)],
            GET_PASSWORD: [MessageHandler(Filters.text, get_password_register, pass_user_data=True)],
            GET_EMAIL: [MessageHandler(Filters.text, get_email_register, pass_user_data=True)]
        },
        fallbacks=[CommandHandler('reset', reset)]
    )

    auth_conversation = ConversationHandler(
        entry_points=[CommandHandler('auth', auth)],
        states={
            GET_LOGIN: [MessageHandler(Filters.text, get_login_auth, pass_user_data=True)],
            GET_PASSWORD: [MessageHandler(Filters.text, get_password_auth, pass_user_data=True)]
        },
        fallbacks=[CommandHandler('reset', reset)]
    )

    find_user_conversation = ConversationHandler(
        entry_points=[CommandHandler('find', find, pass_args=True, pass_user_data=True)],
        states={
            GET_OPPONENT_NAME: [MessageHandler(Filters.text, get_opponent_name, pass_user_data=True)],
            GET_FIND_ACTION: [MessageHandler(Filters.text, user_action, pass_user_data=True)]
        },
        fallbacks=[CommandHandler('reset', reset)]
    )

    game_conversation = ConversationHandler(
        entry_points=[CommandHandler('list', load_games_list, pass_user_data=True)],
        states={
            GET_GAME_ID: [MessageHandler(Filters.text, ask_game, pass_user_data=True)],
            GET_GAME_ACTION: [MessageHandler(Filters.text, game_menu_action, pass_user_data=True)],
            P1Q1: [MessageHandler(Filters.text, p1q1, pass_user_data=True)],
            P1Q2: [MessageHandler(Filters.text, p1q2, pass_user_data=True)],
            P1Q3: [MessageHandler(Filters.text, p1q3, pass_user_data=True)],
            P2Q1: [MessageHandler(Filters.text, p2q1, pass_user_data=True)],
            P2Q2: [MessageHandler(Filters.text, p2q2, pass_user_data=True)],
            P2Q3: [MessageHandler(Filters.text, p2q3, pass_user_data=True)],
            GET_NEXT_CATEGORY: [MessageHandler(Filters.text, set_category, pass_user_data=True)],
            GIVE_UP_CONFIRM: [MessageHandler(Filters.text, give_up_confirm, pass_user_data=True)]
        },
        fallbacks=[CommandHandler('list', load_games_list, pass_user_data=True),
                   CommandHandler('random', start_random_game, pass_user_data=True),
                   CommandHandler('find', find, pass_args=True, pass_user_data=True),
                   CommandHandler('reset', reset)]
    )

    dp.add_handler(CommandHandler('random', start_random_game, pass_user_data=True))
    dp.add_handler(register_conversation)
    dp.add_handler(auth_conversation)
    dp.add_handler(find_user_conversation)
    dp.add_handler(game_conversation)

    try:
        updater.bot.get_me()
        updater.start_polling()
        print('BOT - OK!')

        updater.idle()
    except:
        print('BOT - Error!')


def setup_and_start(token, proxy=True):
    # Указываем настройки прокси (socks5)
    address = "aws.komarov.cf"
    port = 7777
    username = "georgy.komarov"
    password = "08092001"

    updater = Updater(token, request_kwargs={'proxy_url': f'socks5://{address}:{port}/',
                                             'urllib3_proxy_kwargs': {'username': username,
                                                                      'password': password}} if proxy else None)
    print('Proxy - OK!')

    # Запускаем бота
    main(updater)


if __name__ == '__main__':
    TOKEN = '526471154:AAHpXXYOSTU-FR0-l897OWsQO-adfZWU_mk'
    setup_and_start(TOKEN)

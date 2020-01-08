import base64
import hashlib
import hmac
import json
from datetime import datetime

import requests

class DmConnectionHelper:
    def __init__(self):
        # Constants from decompiled Java code
        self.password_salt = 'YhEpgbNqoXOaPXXUxvYm'
        self.hmac_secret = '90zpcNQoNRMRAReL'

        self.base_url = 'https://qkrussia.feogameservercf.com/'
        self.headers = self.set_headers()

    def set_headers(self):
        headers = dict()
        headers['User-Agent'] = 'QuizClash RU A gzip  4.5.1'
        headers['dt'] = 'app'
        headers['Accept-Language'] = 'ru-ru;q=1, en;q=0.9'
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        headers['Connection'] = 'close'
        headers['Accept-Encoding'] = 'gzip, deflate'
        return headers

    @staticmethod
    def get_date():
        date = str(datetime.utcnow())
        return date[:date.index('.')]

    def create_hmac(self, string):
        good_symbols = '-abefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPRSTUXYZ012346789 ,.()'
        base = ''.join(list(filter(lambda x: x in good_symbols, string)))
        for n in [2, 3, 5]:
            base = self.scramble(base, n, 0)
        hmac_base64 = self.hmac_sha256(self.hmac_secret, base)
        return hmac_base64

    def hmac_sha256(self, key, msg):  # str, str
        hmac_bytes = hmac.new(key.encode(), msg=msg.encode(), digestmod=hashlib.sha256).digest()
        hmac_base64 = base64.b64encode(hmac_bytes).decode()
        return hmac_base64

    def scramble(self, string, n, depth):
        depth += 1
        scrambled_string = ''
        middle = len(string) // n
        if middle > 0:
            str1 = string[:middle]
            str2 = string[middle:]
            if depth % 2 == 0:
                scrambled_string += self.scramble(str2, n, depth)
                scrambled_string += self.scramble(str1, n, depth)
            else:
                scrambled_string += self.scramble(str1, n, depth)
                scrambled_string += self.scramble(str2, n, depth)
        else:
            scrambled_string += string
        return scrambled_string

    def md5(self, password_string):
        return hashlib.md5((self.password_salt + password_string).encode()).hexdigest()


class DmServer(DmConnectionHelper):
    def __init__(self):
        super().__init__()
        self.session = requests.Session()

    def restart(self):
        self.session = requests.session()

    def send_request(self, void, params, get=False):
        sorted_params = ''.join(sorted(params.values()))

        date = self.get_date()
        final_url = self.base_url + void + date + sorted_params
        hmac_base64 = self.create_hmac(final_url)
        headers = self.headers
        headers['clientdate'] = date
        headers['hmac'] = hmac_base64
        if get:
            response = self.session.get(url=self.base_url + void, data=params, headers=headers)
        else:
            response = self.session.post(url=self.base_url + void, data=params, headers=headers)
        json_response = json.loads(response.content.decode())
        return json_response

    def create_user(self, username, password, email=None):
        void = 'users/create'
        params = {'name': username, 'pwd': self.md5(password)}
        if email:
            params['email'] = email

        response = self.send_request(void, params)
        return response

    def login(self, username, password):
        void = 'users/login'
        params = {'name': username, 'pwd': self.md5(password)}

        response = self.send_request(void, params)
        return response

    def login_vk(self, vk_access_token, vk_id):
        void = 'users/login_vk_user'
        params = {'vk_id': vk_id, 'vk_access_token': vk_access_token}

        response = self.send_request(void, params)
        return response

    def reload_games_list(self):  # autoLogin
        void = 'users/current_user_games_m'
        params = {}

        return self.send_request(void, params)

    def find_user(self, search_string):
        void = 'users/find_user'
        params = {'opponent_name': search_string}

        return self.send_request(void, params)

    def find_users_vk(self, vk_id, vk_access_token):
        void = 'users/find_users_vk'
        params = {'vk_id': vk_id, 'vk_access_token': vk_access_token}

        return self.send_request(void, params)

    def create_game(self, opponent_id, game_mode='0', was_recommended='0'):
        void = 'games/create_game'
        params = {'opponent_id': opponent_id, 'mode': game_mode, 'was_recommended': was_recommended}

        raw_json = self.send_request(void, params)
        return raw_json

    def start_random_game(self, game_mode='0'):
        void = 'games/start_random_game'
        params = {'mode': game_mode}

        raw_json = self.send_request(void, params)
        return raw_json

    def load_game(self, game_id):
        void = 'games_m'
        params = {'game_id': str(game_id)}

        raw_json = self.send_request(void, params)
        return raw_json

    def upload_round_answers(self, my_answers, question_types, no_images, game_id, cat_id):
        void = 'games/upload_round_answers'
        params = {'answers': my_answers, 'question_types': question_types, 'is_image_question_disabled': no_images,
                  'game_id': game_id, 'cat_choice': cat_id}

        return self.send_request(void, params)
        
    def get_game_stats(self):  # friends stats
        void = 'stats/my_game_stats'
        params = {}

        return self.send_request(void, params, get=True)

    def get_stats(self):  # categories stats
        void = 'stats/my_stats'
        params = {}

        return self.send_request(void, params, get=True)

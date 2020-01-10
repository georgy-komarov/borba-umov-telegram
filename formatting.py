from pygame import Color
from random import shuffle as randomize
from requests import get

QUESTIONS_COUNT = 54
ROUNDS_COUNT = 6
QUESTIONS_PER_ROUND = 3
CATEGORIES_VARIANTS = 3
VARIANTS_COUNT = 4


class DmFormat:
    def __init__(self, response):
        self.response = response['game']
        self.questions = self.response['questions']
        self.image_questions = self.response['image_questions']
        self.questions_sets = []
        self.rounds = []

    def json_to_game(self):
        # TODO Add questions with images
        # if not self.no_images:
        #     self.add_image_questions()
        self.questions = self.questions_dict_to_classes()
        self.questions_sets = self.questions_list_to_q_sets_list()
        self.rounds = self.questions_sets_to_rounds_list()

        return Game(self.response, self.rounds, [q.type for q in self.questions])

    def add_image_questions(self):
        for image_question in self.image_questions:
            index = image_question['index']
            question_dict = image_question['question']
            self.questions[index] = question_dict

    def questions_dict_to_classes(self):
        questions = []
        for question_dict in self.questions:
            questions.append(Question(question_dict))

        return questions

    def questions_list_to_q_sets_list(self):
        question_sets = []
        for q_id in range(0, QUESTIONS_COUNT, QUESTIONS_PER_ROUND):
            question_sets.append(
                QuestionSet(self.questions[q_id].category, self.questions[q_id:q_id + QUESTIONS_PER_ROUND]))
        return question_sets

    def questions_sets_to_rounds_list(self):
        rounds = []
        for round in range(ROUNDS_COUNT):
            rounds.append(
                Round(round + 1, self.questions_sets[
                                 round * QUESTIONS_PER_ROUND:round * QUESTIONS_PER_ROUND + CATEGORIES_VARIANTS],
                      self.response['your_answers'],
                      self.response['opponent_answers']))
        return rounds


class Game:
    def __init__(self, response, rounds_list, question_types):
        self.response = response
        self.opponent_name = self.response['opponent']['name']
        self.id = self.response['game_id']
        self.state = self.response['state']
        self.is_my_turn = self.response['your_turn']
        self.cat_choices = self.response['cat_choices']
        self.no_images = True  # TODO Add questions with images
        self.question_types = question_types
        self.rounds = rounds_list
        self.my_answers_all = self.get_answers(my=True)
        self.opponent_answers_all = self.get_answers()
        self.my_answers = list(filter(lambda x: x is not None, self.my_answers_all))
        self.opponent_answers = list(filter(lambda x: x is not None, self.opponent_answers_all))
        self.current_round = self.get_current_round()
        self.result = None
        self.rating_bonus = None if 'rating_bonus' not in self.response else self.response['rating_bonus']
        self.my_score = self.my_answers.count(0)
        self.opponent_score = self.opponent_answers[:-QUESTIONS_PER_ROUND].count(
            0) if self.is_my_turn else self.opponent_answers.count(0)
        if self.state not in [0, 1, 10]:
            self.is_my_turn = None
            self.result = self.get_result()
            self.rating_bonus = '+' + str(self.rating_bonus) if self.rating_bonus > 0 else str(self.rating_bonus)

    def get_answers(self, my=False):
        answers = []
        for round_ in self.rounds:
            answers.extend(round_.my_answers if my else round_.opponent_answers)
        return answers

    def get_table(self):
        return list(map(lambda r: [list(map(lambda ans: None if ans is None else ans == 0, r.my_answers)),
                                   list(map(lambda ans: None if ans is None or (
                                       r.number >= self.current_round.number if self.is_my_turn else r.number > self.current_round.number)
                                   else ans == 0, r.opponent_answers))], self.rounds))

    def get_result(self):
        if self.state == 6:
            return 'Время вышло'
        elif self.opponent_score == self.my_score:
            return 'Ничья'
        return 'ПОБЕДА!' if self.my_score > self.opponent_score or self.rating_bonus > 0 else 'Поражение'

    def get_round_by_index(self, i):
        return self.rounds[i]

    def get_current_round(self):
        if self.state in [0, 10]:
            return self.rounds[0]
        return self.rounds[(len(self.opponent_answers) // QUESTIONS_PER_ROUND) - 1] if self.opponent_answers else \
            self.rounds[0]

    def round_end(self):
        self.is_my_turn = False
        return str(self.my_answers).replace(' ', ''), str(self.question_types[:len(self.my_answers)]).replace(' ',
                                                                                                              ''), str(
            int(self.no_images)), str(self.id), str(self.current_round.category_index)


class Round:
    def __init__(self, number, questions_sets, my_answers, opponent_answers):
        self.questions = questions_sets
        self.categories_variants = [q_set.category for q_set in questions_sets]
        self.chosen_set = None
        self.category_index = None
        self.number = number
        self.my_answers = self.set_answers(my_answers)
        self.opponent_answers = self.set_answers(opponent_answers)

    def set_answers(self, answers):
        if len(answers) >= self.number * QUESTIONS_PER_ROUND:
            return answers[(self.number - 1) * QUESTIONS_PER_ROUND:self.number * QUESTIONS_PER_ROUND]
        return [None, None, None]

    def get_questions(self):
        for cat_index, q_set in enumerate(self.questions):
            if q_set.category == self.chosen_category:
                self.chosen_set = q_set
                self.category_index = cat_index
                return q_set

    def get_questions_types(self):
        return [question.type for question in self.chosen_set]

    def set_category(self, category):
        self.chosen_category = category

    def set_category_by_index(self, index):
        self.chosen_category = self.categories_variants[index]

    def set_category_by_name(self, string):
        for category in self.categories_variants:
            if category.name == string:
                self.chosen_category = category
                return True  # for Telegram check
        return False


class QuestionSet:
    def __init__(self, category, questions):
        self.category = category
        self.questions = questions

    def __getitem__(self, item):
        return self.questions[item]


class Question:
    def __init__(self, params_dict):
        self.id = params_dict['q_id']
        self.answer_time = params_dict['answer_time']
        self.question_text = params_dict['question']
        self.category = Category(params_dict['cat_id'], params_dict['cat_name'], params_dict['category']['color'])
        self.answers = [
            Answer(id_=0, text=params_dict['correct'], stats=params_dict['stats']['correct_answer_percent'],
                   correct=True),
            Answer(id_=1, text=params_dict['wrong1'], stats=params_dict['stats']['wrong1_answer_percent']),
            Answer(id_=2, text=params_dict['wrong2'], stats=params_dict['stats']['wrong2_answer_percent']),
            Answer(id_=3, text=params_dict['wrong3'], stats=params_dict['stats']['wrong3_answer_percent'])]
        self.rand_answers = self.answers[:]
        randomize(self.rand_answers)
        if 'image_url' in params_dict.keys():
            self.type = 1
            self.image = self.load_image_from_url(params_dict['image_url'])
        else:
            self.type = 0

    @staticmethod
    def load_image_from_url(url):
        return get(url).content

    def get_correct_answer(self):
        return self.answers[0]

    def get_correct_answer_i(self):
        for ans_i, ans in enumerate(self.rand_answers):
            if ans.id == 0:
                return ans_i

    def get_answer_id_by_string(self, string):
        for ans_i, ans in enumerate(self.answers):
            if string == ans.text:
                return ans_i
        else:
            return 6

    def __str__(self):
        return '{}, {}, {}'.format(self.question_text, self.category, self.answers)


class Answer:
    def __init__(self, id_, text, stats, correct=False):
        self.id = id_
        self.text = text
        self.stats_percent = stats
        self.correct = correct

    def __str__(self):
        return '{}, {}, {}%'.format(self.text, self.correct, self.stats_percent)


class Category:
    def __init__(self, id_, name, color):
        self.cat_id = id_
        self.name = name
        self.color = Color(color)
        # self.color = (self.color.r, self.color.g, self.color.b)

    def __str__(self):
        return self.name

import random
import datetime
from dotenv import load_dotenv
import os

load_dotenv()
from sys import stderr

import certifi
import pymongo as pymongo
from bson import ObjectId

# TOKEN = environ["TOKEN"][:-1].strip()  # '5791033550:AAF_2TRXtRpZa1MqG7g-53pJTQItZVLbY3c'
TOKEN = os.getenv('BOT_TOKEN')
print(TOKEN, file=stderr)
client = pymongo.MongoClient(
	os.getenv('MONGODB_TOKEN'),
	tlsCAFile=certifi.where())
database = client["RandomCoffee"]
users = database["users"]
questions = database["questions"]
tags = database["tags"]
matches = database["matches"]
common_information = database["common_information"]


class Config:
	def __init__(self):
		self.constants = common_information.find_one({"bot_id": TOKEN})

	def __getattr__(self, item):
		return self.constants.get(item)


cfg = Config()


def get_rate_for_pair(user1, user2):
	return random.randint(1, 100)


def insert_user(user):
	users.insert_one(user)


def find_user(tid: int, bot_id: str):
	user = users.find_one({"tid": tid, "bot_id": bot_id})
	if user is None:
		user = {
			"tid": tid,
			"bot_id": bot_id,
			"state": cfg.START_QUESTION,
			"last_question": cfg.START_QUESTION,
			"data": {},
			"waiting_match": False,
		}
		insert_user(user)
	return user


def update_user(user: dict, bot_id: str):
	users.update_one({"tid": user["tid"], "bot_id": bot_id}, {"$set": user})


def find_question(question_id: ObjectId):
	return questions.find_one({"_id": question_id})


def find_data_questions():
	return sorted(filter(lambda x: x.get("title_edit"), questions.find({})), key=lambda x: x.get("title_edit"))


def get_user_data(tid, bot_id):
	def load_data(data):
		if isinstance(data, str):
			return data
		return find_tag(data)["name"]

	user = find_user(tid, bot_id)
	text = '\n'.join(
		f'<b>{x["title_edit"]}:</b> {load_data(user["data"][str(x["_id"])])}'
		for x in find_data_questions()
	)
	return text


def get_profile(tid: int, bot_id: str):
	return f'<b>{cfg.TEXT_PROFILE}</b>\n{get_user_data(tid, bot_id)}'


def get_user_name(tid: int, bot_id: str):
	user_data = find_user(tid, bot_id).get('data', dict())
	for key in user_data:
		if ObjectId(key) == cfg.NAME_QUESTION:
			return user_data[key]
	return 'пользователь'


def get_match_profile(tid: int, bot_id: str):
	username = f'<a href="tg://user?id={tid}">{get_user_name(tid, bot_id)}</a>'
	return f'{cfg.SCHEDULE_TEXTS[-1]} {username}\n{get_user_data(tid, bot_id)}'


def find_tag(tag_id):
	return tags.find_one(tag_id)


def find_match(match_id):
	return matches.find_one(match_id)


def find_users_waiting_match():
	users_waiting_match = users.find({"waiting_match": True})
	return users_waiting_match


def find_user_not_waiting_match():
	user_not_waiting_match = users.find({"waiting_match": False})
	return user_not_waiting_match


def insert_match_in_user(user_id, bot_id, match_id):
	users.update_one({"tid": user_id, "bot_id": bot_id}, {"$push": {"matches": match_id}}, upsert=True)


def insert_match(user1_id, user2_id, bot_id):
	match = matches.insert_one({
		"users": [user1_id, user2_id],
		"time": datetime.datetime.now(),
		"delivered": False,
	})
	inserted_id = match.inserted_id
	insert_match_in_user(user1_id, bot_id, inserted_id)
	insert_match_in_user(user2_id, bot_id, inserted_id)


def update_match(match):
	matches.update_one({"_id": match["_id"]}, {"$set": match})


def find_all_matches():
	return matches.find({"delivered": False})

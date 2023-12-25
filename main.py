import os
import logging
import asyncio

import aioschedule
from aiogram import Dispatcher, Bot
from aiogram.types import ChatPermissions
from aiogram.utils import executor
from aiogram.types import (
	Message, ContentType, PreCheckoutQuery, CallbackQuery, InlineKeyboardMarkup,
	InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice,
)
from freezegun import freeze_time

import db
from db import cfg


logging.basicConfig(level=logging.INFO)
bot = Bot(token=cfg.bot_id)
dp = Dispatcher(bot)


def zip_zip(buttons: list) -> InlineKeyboardMarkup:
	markup = InlineKeyboardMarkup()
	if max(map(lambda x: len(x.text), buttons)) > cfg.MAX_SYMBOLS_ROW:
		for x in buttons:
			markup.add(x)
		return markup
	for x, y in zip(buttons[::2], buttons[1::2]):
		markup.row(x, y)
	if len(buttons) % 1:
		markup.add(buttons[-1])
	return markup


base_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
# base_keyboard.add(KeyboardButton(cfg.BUTTON_MATCH))
base_keyboard.row(KeyboardButton(cfg.BUTTON_PROFILE), KeyboardButton(cfg.BUTTON_SOS))
profile_keyboard = zip_zip(list(map(
	lambda x: InlineKeyboardButton(text=x["title_edit"], callback_data=f'profile:{x["_id"]}'),
	db.find_data_questions()
)))


async def trigger(question_id: db.ObjectId, user: dict):
	if question_id is None:
		await bot.send_message(
			user["tid"],
			db.get_profile(user["tid"], cfg.bot_id),
			parse_mode='html',
			reply_markup=base_keyboard
		)
		return
	question = db.find_question(question_id)
	if question.get("type_answer") is None:
		user["state"] = question.get("next_question")
		if user["last_question"] is not None:
			user["last_question"] = user["state"]
		await bot.send_message(user["tid"], question["text"])
		db.update_user(user, cfg.bot_id)
		await trigger(user["state"], user)
	elif question["type_answer"] == "text":
		await bot.send_message(user["tid"], question["text"])
	elif question["type_answer"] == "single_button":
		await bot.send_message(
			user["tid"],
			question["text"],
			reply_markup=zip_zip(
				list(map(
						lambda x: InlineKeyboardButton(text=db.find_tag(x)["name"], callback_data=str(x)),
						question["fields_answer"]
					))
			)
		)
	elif question.get("type_answer") == "finish":
		user["state"] = question.get("next_question")
		if user["last_question"] is not None:
			user["last_question"] = user["state"]
		await bot.send_message(user["tid"], question["text"])
		db.update_user(user, cfg.bot_id)
		await trigger(user["state"], user)

		faculty = db.find_tag(user["data"]["6588c2e85e82ceb7672e69f7"])["name"]

		print("FACULTY", faculty)

		invite_link = ""

		if faculty == "ПМИ":
			invite_link = "https://t.me/+eMiWFt2yUyE2ZjAy"
			print("IN AMI")
		elif faculty == "ПИ":
			invite_link = "https://t.me/+9cj7JWbWq3M4OThi"
		elif faculty == "ПАД":
			invite_link = "https://t.me/+zkAZAWRGhGc0ZWQy"
		elif faculty == "ЭАД":
			invite_link = "https://t.me/+_5xK2t9PYrBmNjdi"

		inline_kb = InlineKeyboardMarkup().add(InlineKeyboardButton('Присоединиться к чату', url=invite_link))

		print("INVITE LINK", invite_link)

		await bot.send_message(user["tid"], text=f"Вступайте в единомышленников", reply_markup=inline_kb)


@dp.message_handler(content_types=['new_chat_members'])
async def on_user_joins(message: Message):
    new_members = message.new_chat_members
    for member in new_members:
        if not member.is_bot:
            welcome_text = f"Добро пожаловать, {member.full_name}!\n\n{db.get_profile(member.id, cfg.bot_id)}"
            await message.reply(welcome_text,	parse_mode='html')

@dp.message_handler(commands=['start'])
async def start(message: Message):
	user = db.find_user(message.from_user.id, cfg.bot_id)
	await trigger(user["state"], user)


async def go_next(user_id: int, message: Message, data: str, clear_markup: bool = False):
	user = db.find_user(user_id, cfg.bot_id)
	question = db.find_question(user["state"])
	if clear_markup:
		data = db.ObjectId(data)
		await message.edit_text(
			text=f'{message.text}\n\n👉 <b>{db.find_tag(data)["name"]}</b>',
			parse_mode='html',
			reply_markup=None
		)
	user["data"][str(question["_id"])] = data
	if user.get("edit_flag"):
		user["state"] = None
		user["edit_flag"] = False
	else:
		user["state"] = question.get("next_question")
	if user["last_question"] is not None:
		user["last_question"] = user["state"]
	db.update_user(user, cfg.bot_id)
	await trigger(user["state"], user)


@dp.message_handler()
async def message_trigger(message: Message):
	user = db.find_user(message.from_user.id, cfg.bot_id)
	if user["state"] is not None:
		await go_next(message.from_user.id, message, message.text)
	elif message.text == cfg.BUTTON_SOS:
		await message.answer(cfg.TEXT_SOS)
	elif message.text == cfg.BUTTON_PROFILE:
		await message.answer(
			db.get_profile(message.from_user.id, cfg.bot_id),
			parse_mode='html',
			reply_markup=profile_keyboard,
		)



@dp.callback_query_handler(lambda call: call.data.startswith('profile'))
async def profile_edit_button(call: CallbackQuery):
	question_id = db.ObjectId(call.data.split(':')[1])
	user = db.find_user(call.from_user.id, cfg.bot_id)
	user["edit_flag"] = True
	user["state"] = question_id
	db.update_user(user, cfg.bot_id)
	await call.message.edit_reply_markup(None)
	await trigger(question_id, user)


@dp.callback_query_handler()
async def button_trigger(call: CallbackQuery):
	user = db.find_user(call.from_user.id, cfg.bot_id)
	if user["state"] is not None:
		await go_next(call.from_user.id, call.message, call.data, clear_markup=True)


@dp.pre_checkout_query_handler(lambda query: True)
async def pre_checkout_query(pre_checkout_q: PreCheckoutQuery):
	await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
	user = db.find_user(message.from_user.id, cfg.bot_id)
	question = db.find_question(user["state"])
	user["waiting_match"] = True
	user["state"] = question.get("next_question")
	db.update_user(user, cfg.bot_id)
	await bot.send_message(user["tid"], cfg.TEXT_PAID)
	await trigger(user["state"], user)


if __name__ == '__main__':
	try:
		executor.start_polling(dp, skip_updates=True)
	except Exception as exc:
		logging.error(exc)
		os._exit(0)

from http.server import BaseHTTPRequestHandler
import os
import json
import asyncio
import requests
import datetime
from telebot.async_telebot import AsyncTeleBot
import firebase_admin
from firebase_admin import credentials, firestore, storage
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# Initialize bot
BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = AsyncTeleBot(BOT_TOKEN)

# Initialize Firebase
firebase_config = json.loads(os.environ.get('FIREBASE_SERVICE_ACCOUNT'))
cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred, {'storageBucket': 'afri-cloud-app.appspot.com'})

db = firestore.client()
bucket = storage.bucket()

def generate_start_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("open Rush App", web_app=WebAppInfo(url="https://rushminiapp.netlify.app/"))) 
    return keyboard

@bot.message_handler(commands=['start'])
async def start(message):
    user_id = str(message.from_user.id)
    user_first_name = str(message.from_user.first_name)
    user_last_name = message.from_user.last_name or ""
    user_username = message.from_user.username or ""
    user_language_code = str(message.from_user.language_code or "en")
    is_premium = getattr(message.from_user, 'is_premium', False)
    text = message.text.split()
    welcome_message = (
        f"Hi, {user_first_name}! 👋\n\n"
        f"Welcome to Rush App! 🤭\n\n"
        f"Here you can earn Our coin by mining! 😊\n\n"
        f"Invite Friends to earn more coins together, and level up faster! 😊"
    )

    try:
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            photos = await bot.get_user_profile_photos(user_id, limit=1)
            user_image = None
            if photos.total_count > 0:
                file_id = photos.photos[0][-1].file_id
                file_info = await bot.get_file(file_id)
                file_path = file_info.file_path
                file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

                response = requests.get(file_url)
                if response.status_code == 200:
                    blob = bucket.blob(f"user_image/{user_id}.jpg")
                    blob.upload_from_string(response.content, content_type='image/jpeg')
                    user_image = blob.generate_signed_url(datetime.timedelta(days=365), method='GET')

            user_data = {
                'userImage': user_image,
                'firstName': user_first_name,
                'lastName': user_last_name,
                'username': user_username,
                'languageCode': user_language_code,
                'isPremium': is_premium,
                'referrals': {},
                'balance': 0,
                'mineRate': 0.001,
                'isMining': False,
                'miningStartedTime': None,
                'daily': {
                    'claimedTime': None,
                    'claimedDay': 0,
                },
                'links': None,
            }

            if len(text) > 1 and text[1].startswith('ref_'):
                referrer_id = text[1][4:]
                referrer_ref = db.collection('users').document(referrer_id)
                referrer_doc = referrer_ref.get()

                if referrer_doc.exists:
                    user_data['referredBy'] = referrer_id
                    referrer_data = referrer_doc.to_dict()
                    bonus_amount = 500 if is_premium else 100

                    referrer_ref.update({
                        'balance': firestore.Increment(bonus_amount),
                        'referrals': {**referrer_data.get('referrals', {}), user_id: {
                            'addedValue': bonus_amount,
                            'firstName': user_first_name,
                            'lastName': user_last_name,
                            'userImage': user_image,
                        }}
                    })
            user_ref.set(user_data)

        keyboard = generate_start_keyboard()
        await bot.reply_to(message, welcome_message, reply_markup=keyboard)
    except Exception as e:
        await bot.reply_to(message, "Error. please try again")
        import traceback
        print(f"Error: {traceback.format_exc()}")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        update_dict = json.loads(post_data.decode('utf-8'))

        asyncio.run(self.process_update(update_dict))

        self.send_response(200)
        self.end_headers()

    async def process_update(self, update_dict):
        update = types.Update.de_json(update_dict)
        await bot.process_new_updates([update])

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write("Bot is running".encode())
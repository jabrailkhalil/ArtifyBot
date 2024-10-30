from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from image_generator import load_model, generate_image, load_text_processing_model, preprocess_text
import logging
import os
import time

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Отключаем логи библиотеки httpx для уровня INFO и ниже
logging.getLogger("httpx").setLevel(logging.WARNING)

ADMIN_USER_ID = 1 #ID ADMIN

# Храним статус пользователей: True, если пользователь занят, иначе False
user_status = {}
lock_duration = 10  # Блокировка на 10 секунд после генерации изображения

# Загружаем модели
model = load_model()  # Модель для генерации изображений
translation_model = load_text_processing_model()  # Модель для перевода текста

# Функция для отслеживания уникальных пользователей
def track_user(user_id):
    file_path = "users.txt"
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            pass

    with open(file_path, "r") as f:
        users = f.read().splitlines()

    if str(user_id) not in users:
        with open(file_path, "a") as f:
            f.write(f"{user_id}\n")
        logger.info(f"Новый пользователь добавлен: {user_id}")
    else:
        logger.info(f"Пользователь {user_id} уже существует.")

# Функция для получения количества пользователей
def get_user_count():
    file_path = "users.txt"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            users = f.read().splitlines()
        return len(users)
    return 0

# Функция для получения списка всех пользователей
def get_all_users():
    file_path = "users.txt"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            users = f.read().splitlines()
        return users
    return []

# Проверяем, заблокирован ли пользователь
def is_user_blocked(user_id):
    if user_id in user_status:
        block_until = user_status[user_id]
        if time.time() < block_until:
            return True
    return False

# Блокируем пользователя на определённое время
def block_user(user_id, duration):
    user_status[user_id] = time.time() + duration

# Функция для отправки уведомления всем пользователям
async def notify_users(application, message):
    users = get_all_users()
    for user_id in users:
        try:
            await application.bot.send_message(chat_id=user_id, text=message)
            logger.info(f"Сообщение отправлено пользователю {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")

# Команда для уведомления перед выключением
async def shutdown(update: Update, context):
    user_id = update.message.from_user.id
    if user_id == ADMIN_USER_ID:  # Проверка, является ли пользователь администратором
        await notify_users(context.application, "Бот временно выключается. Свяжитесь с администратором для его запуска.")
        logger.info("Уведомление перед выключением отправлено пользователям.")
    else:
        await update.message.reply_text("У вас нет прав на выполнение этой команды.")
        logger.warning(f"Пользователь {user_id} попытался выполнить команду /shutdown.")

# Обработка сообщений от пользователя
async def handle_message(update: Update, context):
    user_id = update.message.from_user.id  # Получаем user_id пользователя
    track_user(user_id)  # Отслеживаем пользователя

    # Проверяем, не заблокирован ли пользователь
    if is_user_blocked(user_id):
        await update.message.reply_text("Неприятно когда спамят? Держи обратно!")
        logger.warning(f"Пользователь {user_id} пытается отправить запрос до завершения предыдущего.")
        return

    # Устанавливаем блокировку пользователя на время генерации
    block_user(user_id, lock_duration)

    try:
        if update.message and update.message.text:  # Проверяем, что сообщение содержит текст
            user_input = update.message.text
            logger.info(f"Получено сообщение от пользователя: {user_input}")

            # Перевод текста
            processed_text = preprocess_text(user_input, translation_model)
            logger.info(f"Обработанный текст для генерации: {processed_text}")

            # Генерация изображения
            image_path = generate_image(processed_text, model)
            logger.info(f"Изображение сгенерировано по запросу: {processed_text}")

            await update.message.reply_photo(photo=open(image_path, 'rb'))
            logger.info(f"Изображение отправлено пользователю.")
        else:
            await update.message.reply_text('Пожалуйста, отправьте текст для генерации изображения.')
            logger.info("Получено сообщение без текста.")
    finally:
        # Освобождаем статус пользователя, если это необходимо, или продолжаем блокировку на время
        block_user(user_id, lock_duration)  # Продлеваем блокировку на 10 секунд после завершения

# Приветственное сообщение /start
async def start(update: Update, context):
    await update.message.reply_text(f'Привет! Введи текст для генерации изображения. Сейчас у нас {get_user_count()} пользователей!')
    logger.info("Бот отправил приветственное сообщение.")

# Уведомление о запуске бота
async def notify_on_start(application):
    await notify_users(application, "Бот снова активен. Вы можете отправлять запросы на генерацию изображений.")
    logger.info("Уведомление о запуске отправлено пользователям.")

# Запуск бота
if __name__ == '__main__':
    print("Запуск бота...")
    application = Application.builder().token("<telegramAPI:key>").build()

    # Уведомление пользователей при запуске
    application.post_init = notify_on_start

    # Команда для отправки уведомления перед выключением
    shutdown_handler = CommandHandler('shutdown', shutdown)
    application.add_handler(shutdown_handler)

    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)

    message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    application.add_handler(message_handler)

    print("Бот запущен, ожидаю сообщения...")
    # Постоянное прослушивание сообщений
    application.run_polling()
from transformers import pipeline
from diffusers import StableDiffusionPipeline
import torch
import logging

# Включаем логирование
logger = logging.getLogger(__name__)


# Загрузка модели для перевода текста
def load_text_processing_model():
    logger.info("Загружаем модели для перевода.")
    translation_model = pipeline("translation_ru_to_en", model="Helsinki-NLP/opus-mt-ru-en",
                                 device=0)  # Явно указываем использование GPU (device=0)
    logger.info("Модели загружены.")
    return translation_model


# Перевод текста
def preprocess_text(prompt, translation_model):
    logger.info(f"Переводим текст: {prompt}")
    translated_text = translation_model(prompt, max_length=100)[0]['translation_text']
    logger.info(f"Текст переведён: {translated_text}")
    return translated_text


# Загрузка модели для генерации изображений
def load_model():
    logger.info("Загружаем модель для генерации изображений на GPU.")
    # Явно указываем использование float16 для экономии видеопамяти, если это требуется
    pipe = StableDiffusionPipeline.from_pretrained("runwayml/stable-diffusion-v1-5", torch_dtype=torch.float16)

    # Переключаем модель на использование GPU
    pipe = pipe.to("cuda")
    logger.info("Модель загружена и работает через GPU.")
    return pipe


# Генерация изображения
def generate_image(prompt, model):
    logger.info(f"Генерация изображения по запросу: {prompt}")

    # Генерируем изображение через модель на GPU
    image = model(prompt).images[0]

    image_path = "generated_image.png"
    image.save(image_path)
    logger.info(f"Изображение сохранено: {image_path}")
    return image_path

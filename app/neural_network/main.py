import cv2
import numpy as np
import tensorflow as tf
import tensorflow_hub as hub
import logging
import os
import warnings
from mido import MidiFile, MidiTrack, Message

# Отключение лишних логов и предупреждений
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Отключает все сообщения TensorFlow, кроме ошибок
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Отключает oneDNN

import absl.logging
absl.logging.set_verbosity(absl.logging.ERROR)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы
FREQ = {
    "C1": 32, "C#1": 34, "D1": 36, "D#1": 38, "E1": 41, "F1": 43, "F#1": 46, "G1": 49,
    "G#1": 52, "A1": 55, "A#1": 58, "B1": 61, "C2": 65, "C#2": 69, "D2": 73, "D#2": 77,
    "E2": 82, "F2": 87, "F#2": 92, "G2": 98, "G#2": 104, "A2": 110, "A#2": 116, "B2": 123,
    "C3": 130, "C#3": 138, "D3": 146, "D#3": 155, "E3": 164, "F3": 174, "F#3": 185, "G3": 196,
    "G#3": 208, "A3": 220, "A#3": 233, "B3": 246, "C4": 261, "C#4": 277, "D4": 293, "D#4": 311,
    "E4": 329, "F4": 349, "F#4": 369, "G4": 392, "G#4": 415, "A4": 440, "A#4": 466, "B4": 493,
    "C5": 523, "C#5": 554, "D5": 587, "D#5": 622, "E5": 659, "F5": 698, "F#5": 739, "G5": 784,
    "G#5": 830, "A5": 880, "A#5": 932, "B5": 987,
}

# Загрузка модели детекции
detector = hub.load("https://tfhub.dev/tensorflow/faster_rcnn/inception_resnet_v2_640x640/1")

def detect_notes_on_single_image(image_path, threshold=0.01):
    """
    Обнаруживает ноты на изображении с использованием модели детекции.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Изображение по пути {image_path} не найдено.")

    img_resized = cv2.resize(img, (320, 320))  # Можно поэкспериментировать с размером
    img_tensor = tf.convert_to_tensor(img_resized, dtype=tf.uint8)
    img_tensor = tf.expand_dims(img_tensor, axis=0)

    result = detector(img_tensor)
    boxes = result["detection_boxes"].numpy()[0]
    scores = result["detection_scores"].numpy()[0]

    valid_boxes = boxes[scores > threshold]
    logger.info(f"Обнаружено {len(valid_boxes)} объектов с уверенностью выше {threshold}.")
    return valid_boxes, img

def crop_notes(image, boxes):
    """
    Обрезает изображения нот на основе bounding boxes.
    """
    height, width, _ = image.shape
    cropped_notes = []

    for box in boxes:
        ymin, xmin, ymax, xmax = box
        x1, y1, x2, y2 = int(xmin * width), int(ymin * height), int(xmax * width), int(ymax * height)
        cropped_note = image[y1:y2, x1:x2]
        cropped_notes.append(cropped_note)

    return cropped_notes

def process_image(image_path):
    """
    Преобразует изображение в формат, подходящий для модели детекции.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Изображение по пути {image_path} не найдено.")
    img_resized = cv2.resize(img, (320, 320))
    img_tensor = tf.convert_to_tensor(img_resized, dtype=tf.uint8)
    img_tensor = tf.expand_dims(img_tensor, axis=0)
    return img_tensor

def load_model(model_path):
    """
    Загружает обученную модель из файла.
    """
    try:
        model = tf.keras.models.load_model(model_path)
        logger.info(f"Модель успешно загружена из {model_path}.")
        return model
    except Exception as e:
        logger.error(f"Ошибка при загрузке модели: {e}")
        raise

def classify_notes_batch(cropped_notes, classification_model, class_indices):
    """
    Классифицирует ноты в пакетном режиме для ускорения.
    """
    note_labels = []
    batch_notes = np.array([cv2.resize(note, (128, 128)) / 255.0 for note in cropped_notes])
    batch_notes = batch_notes[..., np.newaxis]  # Добавляем каналы для грейскейл

    predictions = classification_model.predict(batch_notes)
    for prediction in predictions:
        note_label = list(class_indices.keys())[np.argmax(prediction)]  # Получаем метку с наибольшей вероятностью
        note_labels.append(note_label)

    return note_labels

def classify_and_convert_to_midi(cropped_notes, classification_model, class_indices, output_midi_path):
    """
    Классифицирует ноты и преобразует их в MIDI-файл.
    """
    try:
        note_labels = classify_notes_batch(cropped_notes, classification_model, class_indices)

        # Создание MIDI-файла
        midi = MidiFile()
        track = MidiTrack()
        midi.tracks.append(track)

        for note_label in note_labels:
            frequency = FREQ.get(note_label, 440)  # Используйте частоту по умолчанию, если нота не найдена
            midi_note = int(69 + 12 * np.log2(frequency / 440))
            track.append(Message('note_on', note=midi_note, velocity=64, time=0))
            track.append(Message('note_off', note=midi_note, velocity=64, time=480))

        # Сохранение MIDI-файла
        midi.save(output_midi_path)
        logger.info(f"MIDI-файл сохранен по пути: {output_midi_path}")

    except Exception as e:
        logger.error(f"Ошибка при создании MIDI-файла: {e}")
        raise

def main(image_path, model_path, class_indices, output_midi_path):
    try:
        # Проверка существования изображения
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Изображение {image_path} не найдено.")

        # Шаг 1: Обнаружение нот на изображении
        logger.info("Обнаружение нот на изображении...")
        boxes, image = detect_notes_on_single_image(image_path, threshold=0.01)
        logger.info(f"Обнаружено bounding boxes: {len(boxes)}")

        if len(boxes) == 0:
            logger.warning("На изображении не обнаружено объектов. Проверьте изображение и порог уверенности.")
            return

        # Шаг 2: Загрузка модели классификатора
        logger.info("Загрузка модели классификатора...")
        model = load_model(model_path)

        # Шаг 3: Обрезка изображений нот
        logger.info("Обрезка изображений нот...")
        cropped_notes = crop_notes(image, boxes)
        for i, note in enumerate(cropped_notes):
            cv2.imwrite(f"note_{i}.png", note)  # Сохраняет обрезанные ноты в файлы

        # Шаг 4: Классификация нот и создание MIDI-файла
        logger.info("Классификация нот и создание MIDI-файла...")
        classify_and_convert_to_midi(cropped_notes, model, class_indices, output_midi_path)

        logger.info("Пайплайн успешно завершен.")

    except Exception as e:
        logger.error(f"Ошибка в пайплайне: {e}")

if __name__ == "__main__":
    # Параметры
    IMAGE_PATH = r"D:\Projects\BRIGADA2-1.png"  # Укажите путь к изображению
    MODEL_PATH = r"D:\Projects\trained_model.h5"  # Укажите путь к модели
    CLASS_INDICES = {
        "C1": 0, "C#1": 1, "D1": 2, "D#1": 3, "E1": 4, "F1": 5, "F#1": 6, "G1": 7,
        "G#1": 8, "A1": 9, "A#1": 10, "B1": 11, "C2": 12, "C#2": 13, "D2": 14, "D#2": 15,
        "E2": 16, "F2": 17, "F#2": 18, "G2": 19, "G#2": 20, "A2": 21, "A#2": 22, "B2": 23,
        "C3": 24, "C#3": 25, "D3": 26, "D#3": 27, "E3": 28, "F3": 29, "F#3": 30, "G3": 31,
        "G#3": 32, "A3": 33, "A#3": 34, "B3": 35, "C4": 36, "C#4": 37, "D4": 38, "D#4": 39,
        "E4": 40, "F4": 41, "F#4": 42, "G4": 43, "G#4": 44, "A4": 45, "A#4": 46, "B4": 47,
        "C5": 48, "C#5": 49, "D5": 50, "D#5": 51, "E5": 52, "F5": 53, "F#5": 54, "G5": 55,
        "G#5": 56, "A5": 57, "A#5": 58, "B5": 59,
    }
    OUTPUT_MIDI_PATH = r"output.mid"  # Укажите путь для сохранения MIDI-файла

    # Запуск пайплайна
    main(IMAGE_PATH, MODEL_PATH, CLASS_INDICES, OUTPUT_MIDI_PATH)
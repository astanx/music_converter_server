from fastapi import APIRouter, UploadFile, File, Response, Request
from typing import List
from pydub import AudioSegment
from midi2audio import FluidSynth
import os
from app.database.connection import database
from app.neural_network.main import classify_and_convert_to_midi, load_model
router = APIRouter()
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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'neural_network', 'trained_model.h5')

@router.post("/music_converter/{userId}")
async def convert_music(request: Request, userId: int, files: List[UploadFile] = File(...)):
    output_directory = "output"
    os.makedirs(output_directory, exist_ok=True)
    wav_files = []
    soundfont_path = os.path.join(BASE_DIR, 'GeneralUser-GS.sf2')
    fs = FluidSynth(soundfont_path)
    
    for file in files:
        contents = await file.read()
        temp_image_path = os.path.join(output_directory, file.filename)

        with open(temp_image_path, 'wb') as f:
            f.write(contents)

        try:
            # Загрузка модели классификации
            classification_model = load_model(MODEL_PATH)  # Используем os для построения пути к модели
            output_midi_path = os.path.join(output_directory, f"{os.path.splitext(file.filename)[0]}.mid")

            # Классификация и преобразование в MIDI
            classify_and_convert_to_midi([temp_image_path], classification_model, CLASS_INDICES, output_midi_path)

            # Конвертация MIDI в WAV
            wav_filename = f"{os.path.splitext(file.filename)[0]}.wav"
            wav_file_path = os.path.join(output_directory, wav_filename)

            fs.midi_to_audio(output_midi_path, wav_file_path)  # Конвертация в WAV
            wav_files.append(wav_file_path)

        except Exception as e:
            return {"message": str(e), "error": True}
        finally:
            os.remove(temp_image_path)

    combined = AudioSegment.empty()
    for wav_file in wav_files:
        audio_segment = AudioSegment.from_wav(wav_file)
        combined += audio_segment 

    output_filename = "combined_output.wav"
    output_path = os.path.join(output_directory, output_filename)

    try:
        combined.export(output_path, format="wav")
    except Exception as e:
        return {"message": str(e), "error": True}

    for wav_file in wav_files:
        os.remove(wav_file)

    with open(output_path, 'rb') as f:
        music_data = f.read()

    query = "INSERT INTO history (userid, music) VALUES (:userid, :music) RETURNING id"
    id = await database.execute(query=query, values={"userid": userId, "music": music_data})

    url = f"{request.url.scheme}://{request.url.netloc}/music/{id}"

    update_query = "UPDATE history SET url = :url WHERE id = :id"
    await database.execute(query=update_query, values={"url": url, "id": id})

    os.remove(output_path)

    return {"url": url, "error": False, "message": "Convert successful"}
@router.get("/{id}")
async def get_file(id: int):
    query = "SELECT music FROM history WHERE id = :id"
    music_record = await database.fetch_one(query=query, values={"id": id})

    if not music_record:
        return {"error": True, "message": "Music record not found."}

    music_data = music_record["music"]

    return Response(content=music_data, media_type="audio/wav")

@router.get("/history/{userId}")
async def get_history(userId: int, page: int = 1, pageSize: int = 3):
    if page > 0:
        offset = (page - 1) * pageSize
    else: 
        offset = 1
    
    count_query = "SELECT COUNT(*) FROM history WHERE userid = :userid"
    total_count = await database.fetch_val(count_query, values={"userid": userId})
    
    query = "SELECT id, url FROM history WHERE userid = :userid LIMIT :limit OFFSET :offset"
    history = await database.fetch_all(query=query, values={"userid": userId, "limit": pageSize, "offset": offset})
    result = [{"id": item["id"], "url": item["url"]} for item in history]
    
    total_pages = (total_count + pageSize - 1) // pageSize  
    
    return {
        "url": result,
        "error": False,
        "message": "Successful",
        "totalCount": total_count,
        "totalPages": total_pages
    }

@router.delete("/history/{userId}/{id}")
async def delete_file(userId: int, id: int, pageSize: int = 3): 
    query = "DELETE FROM history WHERE id = :id"
    try:
        result = await database.execute(query=query, values={"id": id})
        
        count_query = "SELECT COUNT(*) FROM history WHERE userid = :userId"
        total_count = await database.fetch_val(count_query, values={"userid": userId})
    
        total_pages = (total_count + pageSize - 1) // pageSize  
        if result == 0:
            return {"error": True, "message": "No record found to delete"}
        
        return {"error": False, "message": "Successful", "totalPages": total_pages, "totalCount": total_count}
    except Exception as e:
        return {"error": True, "message": str(e)}
from fastapi import APIRouter, UploadFile, File, Response, Request
from typing import List
from fastapi.responses import StreamingResponse
from pydub import AudioSegment
import base64, os, subprocess
from app.database.connection import database


router = APIRouter()

@router.post("/music_converter/{userId}")
async def convert_music(request: Request, userId: int, files: List[UploadFile] = File(...)):
    soundfont_path = os.path.join(os.path.dirname(__file__), 'GeneralUser-GS.sf2')
    wav_files = []

    output_directory = "output"
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    for file in files:
        contents = await file.read()
        
        temp_midi_path = os.path.join(output_directory, file.filename)
        with open(temp_midi_path, 'wb') as f:
            f.write(contents)

        output_format = 'wav'
        wav_filename = f"{os.path.splitext(file.filename)[0]}.{output_format}"
        wav_file_path = os.path.join(output_directory, wav_filename)

       
        try:
            subprocess.run(['fluidsynth', '-ni', soundfont_path, temp_midi_path, '-F', wav_file_path, '-n', 'audio.file-format=wav'], check=True)
            wav_files.append(wav_file_path) 
        except subprocess.CalledProcessError as e:
            return {"message": str(e), "error": True}
        finally:
            os.remove(temp_midi_path)  

    combined = AudioSegment.empty()
    for wav_file in wav_files:
        audio_segment = AudioSegment.from_wav(wav_file)
        combined += audio_segment 

    output_filename = f"combined_output.wav"
    output_path = os.path.join(output_directory, output_filename)

    try:
        combined.export(output_path, format="wav")
    except Exception as e:
        return {"message": str(e), "error": True}

    for wav_file in wav_files:
        os.remove(wav_file)

    with open(output_path, 'rb') as f:
        music_data = f.read()

    query = "INSERT INTO history (userId, music) VALUES (:userId, :music) RETURNING id"
    id = await database.execute(query=query, values={"userId": userId, "music": music_data})
    
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
    
    count_query = "SELECT COUNT(*) FROM history WHERE userId = :userId"
    total_count = await database.fetch_val(count_query, values={"userId": userId})
    
    query = "SELECT id, url FROM history WHERE userId = :userId LIMIT :limit OFFSET :offset"
    history = await database.fetch_all(query=query, values={"userId": userId, "limit": pageSize, "offset": offset})
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
        
        count_query = "SELECT COUNT(*) FROM history WHERE userId = :userId"
        total_count = await database.fetch_val(count_query, values={"userId": userId})
    
        total_pages = (total_count + pageSize - 1) // pageSize  
        if result == 0:
            return {"error": True, "message": "No record found to delete"}
        
        return {"error": False, "message": "Successful", "totalPages": total_pages, "totalCount": total_count}
    except Exception as e:
        return {"error": True, "message": str(e)}
    
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import os
import shutil
from typing import List, Dict, Any
import uuid
from datetime import datetime

app = FastAPI(title="Photo Map Organizer API", version="1.0.0")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base path configuration - ADJUST BASED ON MY ENV
BASE_PATH = Path("/content")

# Mount static files to serve images
if not (BASE_PATH / "static").exists():
    (BASE_PATH / "static").mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(BASE_PATH / "static")), name="static")

# Pydantic models for request/response validation
class FolderRequest(BaseModel):
    country: str
    city: str
    year: int
class MoveImageRequest(BaseModel):
    imageId: str
    country: str
    city: str
    year: int
    sourceFolder: str
class ImageResponse(BaseModel):
    id: str
    name: str
    url: str
    year: int
    location: str
    file_size: int
    created_at: str
class FolderResponse(BaseModel):
    success: bool
    folder_path: str
    message: str
class PinData(BaseModel):
    id: str
    country: str
    city: str
    lat: float
    lng: float
    year: int
    imageCount: int



#FAST API Implementations********************************************
@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Photo Map Organizer API is running"}


@app.post("/api/create-folder", response_model=FolderResponse)
async def create_folder(request: FolderRequest):
    """
    Creates a nested folder structure for organizing photos by location and year.
    Args:
        request: FolderRequest containing country, city, and year
    Returns:
        FolderResponse with success status and folder path
    """
    try:
        folder_path = makeFolder(request.country, request.city, request.year)
        return FolderResponse(
            success=True,
            folder_path=str(folder_path),
            message=f"Folder created successfully for {request.city}, {request.country} ({request.year})"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create folder: {str(e)}")


@app.get("/api/get-images/{year}/{country}/{city}", response_model=List[ImageResponse])
async def get_images(year: int, country: str, city: str):
    """
    Retrieves all images from a specific location and year folder.
    Args:
        year: The year
        country: The country name
        city: The city name
    Returns:
        List of ImageResponse objects with metadata
    """
    try:
        images = viewFolder(country, city, year)
        return images
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve images: {str(e)}")


@app.post("/api/move-image")
async def move_image(request: MoveImageRequest):
    """
    Moves an image from source folder to destination folder based on location.
    Args:
        request: MoveImageRequest with image details and destination
    Returns:
        Success response with move operation details
    """
    try:
        moveFolder(request.imageId, request.country, request.city, request.year, request.sourceFolder)
        return {
            "success": True,
            "message": f"Successfully moved {request.imageId} to {request.city}, {request.country} ({request.year})"
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to move image: {str(e)}")


@app.post("/api/sort-folder")
async def sort_folder_by_date(request: FolderRequest):
    """
    Sorts images in a folder by modification date and renames them with numerical prefixes.
    Args:
        request: FolderRequest specifying the folder to sort
    Returns:
        Success response with sorting details
    """
    try:
        folder_path = BASE_PATH / str(request.year) / request.country / request.city
        if not folder_path.exists():
            raise HTTPException(status_code=404, detail="Folder not found")
        
        sortDate(str(folder_path))
        return {
            "success": True,
            "message": f"Successfully sorted images in {request.city}, {request.country} ({request.year})"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sort folder: {str(e)}")


@app.post("/api/upload-images")
async def upload_images(
    files: List[UploadFile] = File(...),
    country: str = Form(...),
    city: str = Form(...),
    year: int = Form(...)
):
    """
    Uploads multiple images to a specific location folder.
    Args:
        files: List of uploaded image files
        country: Destination country
        city: Destination city
        year: Destination year
    Returns:
        Success response with upload details
    """
    try:
        # Create folder if it doesn't exist
        folder_path = makeFolder(country, city, year)
        uploaded_files = []
        
        for file in files:
            # Generate unique filename to avoid conflicts
            file_extension = Path(file.filename).suffix
            unique_filename = f"{uuid.uuid4().hex}{file_extension}"
            file_path = folder_path / unique_filename
            
            # Save uploaded file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            uploaded_files.append({
                "original_name": file.filename,
                "saved_as": unique_filename,
                "path": str(file_path)
            })
        
        return {
            "success": True,
            "message": f"Successfully uploaded {len(files)} images to {city}, {country} ({year})",
            "uploaded_files": uploaded_files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload images: {str(e)}")


@app.get("/api/get-all-pins", response_model=List[PinData])
async def get_all_pins():
    """
    Retrieves all location pins with their image counts.
    Returns:
        List of PinData objects representing all locations with photos
    """
    try:
        pins = []
        if not BASE_PATH.exists():
            return pins
        
        # Traverse the directory structure to find all locations
        for year_dir in BASE_PATH.iterdir():
            if year_dir.is_dir() and year_dir.name.isdigit():
                year = int(year_dir.name)
                for country_dir in year_dir.iterdir():
                    if country_dir.is_dir():
                        country = country_dir.name
                        for city_dir in country_dir.iterdir():
                            if city_dir.is_dir():
                                city = city_dir.name
                                # Count images in this location
                                image_count = len([f for f in city_dir.iterdir() if f.is_file()])
                                
                                # Generate a unique ID for this pin
                                pin_id = f"{country}_{city}_{year}".replace(" ", "_")
                                
                                pins.append(PinData(
                                    id=pin_id,
                                    country=country,
                                    city=city,
                                    lat=0.0,  # You'll need to add geocoding for real coordinates
                                    lng=0.0,  # You'll need to add geocoding for real coordinates
                                    year=year,
                                    imageCount=image_count
                                ))
        return pins
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve pins: {str(e)}")


@app.get("/api/serve-image/{year}/{country}/{city}/{filename}")
async def serve_image(year: int, country: str, city: str, filename: str):
    """
    Serves an image file from the organized folder structure.
    Args:
        year: The year
        country: The country name
        city: The city name
        filename: The image filename
    Returns:
        FileResponse with the requested image
    """
    try:
        file_path = BASE_PATH / str(year) / country / city / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")
        
        return FileResponse(str(file_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to serve image: {str(e)}")



# Implementation of backend python utility functions****************************************

def makeFolder(country: str, city: str, year: int) -> Path:
    """
    Creates a nested folder structure within the specified environment.
    Args:
        country: The country name
        city: The city name
        year: The year
    Returns:
        Path object of the created folder
    """
    folder_path = BASE_PATH / str(year) / country / city
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path


def sortDate(path: str) -> None:
    """
    Sorts files in a directory by their modification date and renames them
    with a numerical prefix to reflect the sorted order.
    Args:
        path: The path to the directory containing the files
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Directory {path} does not exist")
    
    files = [f for f in path.iterdir() if f.is_file()]
    files.sort(key=lambda x: os.path.getmtime(x))

    # Rename files with a numerical prefix to reflect the sorted order
    for i, old_file_path in enumerate(files):
        # Skip files that already have the naming convention
        if not old_file_path.name.startswith(f"{i+1:03d}_"):
            new_file_name = f"{i+1:03d}_{old_file_path.name}"
            new_file_path = path / new_file_name
            # Handle naming conflicts
            counter = 1
            while new_file_path.exists():
                new_file_name = f"{i+1:03d}_{counter}_{old_file_path.name}"
                new_file_path = path / new_file_name
                counter += 1
            
            os.rename(old_file_path, new_file_path)


def moveFolder(imageId: str, destination_folder: str, sourceFolder: str) -> None:
    """
    Moves an image file from a source folder to a destination folder based on location.
    Args:
        imageId: The name of the image file
        destination_folder: The path to the destination folder where the image is retrieved
        sourceFolder: The path to the source folder where the image is located
    """
    source_path = Path(sourceFolder) / imageId
    
    # Create destination folder if it doesn't exist
    if not destination_folder.exists():
        destination_folder.mkdir(parents=True, exist_ok=True)
    
    destination_path = destination_folder / imageId
    
    # Handle naming conflicts
    counter = 1
    while destination_path.exists():
        name_parts = Path(imageId).stem, Path(imageId).suffix
        new_name = f"{name_parts[0]}_{counter}{name_parts[1]}"
        destination_path = destination_folder / new_name
        counter += 1
    
    # Move the file
    if not source_path.exists():
        raise FileNotFoundError(f"Source file '{imageId}' not found in '{sourceFolder}'")
    
    shutil.move(str(source_path), str(destination_path))


def viewFolder(country: str, city: str, year: int) -> List[Dict[str, Any]]:
    """
    Retrieves image files from a specified folder and returns a list of image objects with metadata.
    Args:
        country: The country name
        city: The city name
        year: The year
    Returns:
        A list of dictionaries representing images with metadata
    """
    folder_path = BASE_PATH / str(year) / country / city
    image_list = []

    if folder_path.exists() and folder_path.is_dir():
        for file_path in folder_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                # Get file stats
                stats = file_path.stat()
                created_time = datetime.fromtimestamp(stats.st_mtime).isoformat()
                
                image_list.append({
                    "id": file_path.name,
                    "name": file_path.name,
                    "url": f"/api/serve-image/{year}/{country}/{city}/{file_path.name}",
                    "year": year,
                    "location": city,
                    "file_size": stats.st_size,
                    "created_at": created_time
                })
    
    return image_list


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

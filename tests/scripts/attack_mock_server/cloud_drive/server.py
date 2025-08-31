from config import (SharingPermission, CloudDriveFile, CloudDriveFileID, cloud_drive,
                    SearchFilesByFilename, CreateFile, DeleteFile,
                    GetFileById, ShareFile, AppendToFile,
                    SearchFiles)
from fastapi import FastAPI

app = FastAPI()

@app.post("/search_files_by_filename")
def search_files_by_filename(
    req: SearchFilesByFilename
) -> list[CloudDriveFile]:
    """Get a file from a cloud drive by its filename. It returns a list of files.
    Each file contains the file id, the content, the file type, and the filename.

    :param filename: The name of the file to retrieve.
    """
    return cloud_drive.search_files_by_filename(req.filename)

@app.post("/create_file")
def create_file(
    req: CreateFile
) -> CloudDriveFile | dict[str, str]:
    """Create a new file in the cloud drive.

    :param filename: The name of the file to create.
    :param content: The content of the file to create.
    """
    try:
        return cloud_drive.create_file(req.filename, req.content)
    except Exception as e:
        return {
            "error": str(e)
        }

@app.post("/delete_file")
def delete_file(req: DeleteFile) -> CloudDriveFile | dict[str, str]:
    """Delete a file from the cloud drive by its filename.
    It returns the file that was deleted.

    :param file_id: The name of the file to delete.
    """
    try:
        return cloud_drive.delete_file(CloudDriveFileID(req.file_id))
    except Exception as e:
        return {
            "error": str(e)
        }

@app.post("/get_file_by_id")
def get_file_by_id(req: GetFileById) -> CloudDriveFile | dict[str, str]:
    """Get a file from a cloud drive by its ID.

    :param file_id: The ID of the file to retrieve.
    """
    try:
        return cloud_drive.get_file_by_id(req.file_id)
    except Exception as e:
        return {
            "error": str(e)
        }

@app.get("/list_files")
def list_files() -> list[CloudDriveFile]:
    """Retrieve all files in the cloud drive."""
    return list(cloud_drive.files.values())

@app.post("/share_file")
def share_file(
    req: ShareFile
) -> CloudDriveFile:
    """Share a file with a user.

    :param file_id: The ID of the file to share.
    :param email: The email of the user to share the file with.
    :param permission: The permission level to grant the user.
    """
    file = cloud_drive.get_file_by_id(CloudDriveFileID(req.file_id))
    file.shared_with[req.email] = req.permission
    return file

@app.post("/append_to_file")
def append_to_file(
    req: AppendToFile
) -> CloudDriveFile:
    """Append content to a file in the cloud drive.

    :param file_id: The ID of the file to append content to.
    :param content: The content to append to the file.
    """
    return cloud_drive.append_to_file(CloudDriveFileID(req.file_id), req.content)

@app.post("/search_files")
def search_files(req: SearchFiles) -> list[CloudDriveFile] | dict[str, str]:
    """Search for files in the cloud drive by content.

    :param query: The string to search for in the files.
    """
    matches = cloud_drive.search_files(req.query)
    if len(matches) == 0:
        return {
            "error": f"No files found with the given query ('{req.query}'). Try a different search term."
        }
    return matches
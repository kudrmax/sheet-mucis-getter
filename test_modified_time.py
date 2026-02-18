"""
Тест-скрипт: проверяем, меняется ли modifiedTime папки
при добавлении/удалении файлов внутри неё.

Запуск:
    python test_modified_time.py
"""

import time

from google.oauth2 import service_account
from googleapiclient.discovery import build

import config

SCOPES = ["https://www.googleapis.com/auth/drive"]


def get_service():
    creds = service_account.Credentials.from_service_account_file(
        config.CREDENTIALS_PATH, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def get_modified_time(service, folder_id: str) -> str:
    result = (
        service.files()
        .get(fileId=folder_id, fields="modifiedTime")
        .execute()
    )
    return result["modifiedTime"]


def main():
    service = get_service()
    root_id = config.GOOGLE_DRIVE_FOLDER_ID

    print(f"Root folder ID: {root_id}")

    # 1. Получаем modifiedTime
    mt1 = get_modified_time(service, root_id)
    print(f"\n[1] modifiedTime ДО изменений: {mt1}")

    # 2. Создаём тестовый файл внутри папки
    print("\n[2] Создаю тестовый файл в папке...")
    from googleapiclient.http import MediaInMemoryUpload

    media = MediaInMemoryUpload(b"test content", mimetype="text/plain")
    test_file = (
        service.files()
        .create(
            body={"name": "_test_cache_check.txt", "parents": [root_id]},
            media_body=media,
            fields="id",
        )
        .execute()
    )
    test_file_id = test_file["id"]
    print(f"   Создан файл: {test_file_id}")

    # Небольшая пауза для синхронизации
    time.sleep(2)

    # 3. Проверяем modifiedTime после добавления
    mt2 = get_modified_time(service, root_id)
    print(f"\n[3] modifiedTime ПОСЛЕ добавления файла: {mt2}")
    print(f"   Изменилось? {'ДА ✓' if mt2 != mt1 else 'НЕТ ✗'}")

    # 4. Удаляем тестовый файл
    print("\n[4] Удаляю тестовый файл...")
    service.files().delete(fileId=test_file_id).execute()
    time.sleep(2)

    # 5. Проверяем modifiedTime после удаления
    mt3 = get_modified_time(service, root_id)
    print(f"\n[5] modifiedTime ПОСЛЕ удаления файла: {mt3}")
    print(f"   Изменилось? {'ДА ✓' if mt3 != mt2 else 'НЕТ ✗'}")

    # Проверяем подпапку — создаём папку, добавляем файл внутрь,
    # проверяем modifiedTime подпапки и корневой папки
    print("\n[6] Проверяю подпапку...")
    subfolder = (
        service.files()
        .create(
            body={
                "name": "_test_subfolder",
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [root_id],
            },
            fields="id",
        )
        .execute()
    )
    subfolder_id = subfolder["id"]
    time.sleep(2)

    mt_sub1 = get_modified_time(service, subfolder_id)
    mt_root_after_subfolder = get_modified_time(service, root_id)
    print(f"   modifiedTime подпапки: {mt_sub1}")
    print(f"   modifiedTime корня после создания подпапки: {mt_root_after_subfolder}")

    # Добавляем файл в подпапку
    print("\n[7] Добавляю файл в подпапку...")
    media2 = MediaInMemoryUpload(b"sub test", mimetype="text/plain")
    sub_file = (
        service.files()
        .create(
            body={"name": "_test_sub_file.txt", "parents": [subfolder_id]},
            media_body=media2,
            fields="id",
        )
        .execute()
    )
    time.sleep(2)

    mt_sub2 = get_modified_time(service, subfolder_id)
    mt_root_after_sub_file = get_modified_time(service, root_id)
    print(f"   modifiedTime подпапки ПОСЛЕ файла: {mt_sub2}")
    print(f"   Подпапка изменилась? {'ДА ✓' if mt_sub2 != mt_sub1 else 'НЕТ ✗'}")
    print(f"   modifiedTime корня ПОСЛЕ файла в подпапке: {mt_root_after_sub_file}")
    print(f"   Корень изменился? {'ДА ✓' if mt_root_after_sub_file != mt_root_after_subfolder else 'НЕТ ✗'}")

    # Cleanup
    print("\n[8] Очистка...")
    service.files().delete(fileId=sub_file["id"]).execute()
    service.files().delete(fileId=subfolder_id).execute()
    print("   Готово!")

    # Итог
    print("\n" + "=" * 50)
    print("ИТОГ:")
    print(f"  Добавление файла меняет modifiedTime папки: {'ДА' if mt2 != mt1 else 'НЕТ'}")
    print(f"  Удаление файла меняет modifiedTime папки:   {'ДА' if mt3 != mt2 else 'НЕТ'}")
    print(f"  Файл в подпапке меняет modifiedTime подпапки: {'ДА' if mt_sub2 != mt_sub1 else 'НЕТ'}")
    print(f"  Файл в подпапке меняет modifiedTime корня:    {'ДА' if mt_root_after_sub_file != mt_root_after_subfolder else 'НЕТ'}")


if __name__ == "__main__":
    main()

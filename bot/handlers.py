import asyncio
import io
import os
import zipfile

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.keyboards import (
    CHOOSE_SHEETS,
    UPLOAD_SHEETS,
    get_confirm_filename_keyboard,
    get_folders_inline_keyboard,
    get_more_files_keyboard,
    get_start_keyboard,
    get_upload_folders_inline_keyboard,
)
from services.drive_service import DriveService

router = Router()


class SheetStates(StatesGroup):
    selecting_folders = State()
    choosing_upload_folder = State()
    entering_new_folder_name = State()
    waiting_for_files = State()
    confirming_filename = State()


# ── Start ──


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Я помогу получить ноты с Google Drive.\n"
        "Нажми кнопку ниже.",
        reply_markup=get_start_keyboard(),
    )


# ── Batch download flow ──


@router.message(F.text == CHOOSE_SHEETS)
async def choose_sheets(
    message: Message, state: FSMContext, drive: DriveService, root_folder_id: str
):
    folders = drive.list_folders(root_folder_id)
    if not folders:
        await message.answer("Папки не найдены.", reply_markup=get_start_keyboard())
        return

    await state.set_state(SheetStates.selecting_folders)
    await state.update_data(folders=folders, selected_ids=[])
    await message.answer(
        "Выберите папки для скачивания:",
        reply_markup=get_folders_inline_keyboard(folders, set()),
    )


@router.callback_query(SheetStates.selecting_folders, F.data.startswith("folder_toggle:"))
async def toggle_folder(callback: CallbackQuery, state: FSMContext):
    folder_id = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = set(data.get("selected_ids", []))

    if folder_id in selected:
        selected.discard(folder_id)
    else:
        selected.add(folder_id)

    await state.update_data(selected_ids=list(selected))
    await callback.message.edit_reply_markup(
        reply_markup=get_folders_inline_keyboard(data["folders"], selected)
    )
    await callback.answer()


@router.callback_query(SheetStates.selecting_folders, F.data == "select_all")
async def select_all_folders(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    folders = data["folders"]
    selected = set(data.get("selected_ids", []))
    all_ids = {f["id"] for f in folders}

    if selected == all_ids:
        selected = set()
    else:
        selected = all_ids

    await state.update_data(selected_ids=list(selected))
    await callback.message.edit_reply_markup(
        reply_markup=get_folders_inline_keyboard(folders, selected)
    )
    await callback.answer()


@router.callback_query(SheetStates.selecting_folders, F.data == "download_selected")
async def download_selected(
    callback: CallbackQuery,
    state: FSMContext,
    drive: DriveService,
):
    data = await state.get_data()
    selected = set(data.get("selected_ids", []))
    folders = data["folders"]

    if not selected:
        await callback.answer("Выберите хотя бы одну папку!", show_alert=True)
        return

    await callback.message.edit_text("Скачиваю файлы...")
    await callback.answer()

    # Collect all download tasks across all selected folders
    all_tasks = []
    selected_folders = [f for f in folders if f["id"] in selected]
    folder_links = []

    for folder in selected_folders:
        files = drive.list_files(folder["id"])
        if not files:
            continue
        link = DriveService.get_folder_link(folder["id"])
        folder_links.append(f'<a href="{link}">{folder["name"]}</a>')
        for file_meta in files:
            all_tasks.append((folder["name"], file_meta))

    if not all_tasks:
        await state.clear()
        await callback.message.edit_text("В выбранных папках нет файлов.")
        await callback.message.answer("Что дальше?", reply_markup=get_start_keyboard())
        return

    async def _download(
        folder_name: str, file_meta: dict
    ) -> tuple[str, bytes, str] | str:
        try:
            content, filename = await asyncio.to_thread(
                drive.download_file, file_meta["id"]
            )
            return folder_name, content, filename
        except Exception as e:
            return f"Не удалось скачать «{file_meta['name']}»: {e}"

    results = await asyncio.gather(
        *[_download(fn, fm) for fn, fm in all_tasks]
    )

    buf = io.BytesIO()
    errors = []
    total = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for result in results:
            if isinstance(result, str):
                errors.append(result)
                continue
            folder_name, content, filename = result
            zf.writestr(f"{folder_name}/{filename}", content)
            total += 1

    for err in errors:
        await callback.message.answer(err)

    if total > 0:
        buf.seek(0)
        caption = "Папки:\n" + "\n".join(folder_links)
        doc = BufferedInputFile(buf.getvalue(), filename="ноты.zip")
        await callback.message.answer_document(
            doc, caption=caption, parse_mode="HTML"
        )

    await state.clear()
    await callback.message.answer(
        f"Отправлено файлов: {total}", reply_markup=get_start_keyboard()
    )


# ── Upload flow ──


@router.message(F.text == UPLOAD_SHEETS)
async def upload_sheets(
    message: Message, state: FSMContext, drive: DriveService, root_folder_id: str
):
    folders = drive.list_folders(root_folder_id)
    await state.set_state(SheetStates.choosing_upload_folder)
    await state.update_data(folders=folders)
    await message.answer(
        "Выберите папку для загрузки или создайте новую:",
        reply_markup=get_upload_folders_inline_keyboard(folders),
    )


@router.callback_query(
    SheetStates.choosing_upload_folder, F.data.startswith("upload_folder:")
)
async def pick_upload_folder(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":", 2)
    folder_id = parts[1]
    folder_name = parts[2]

    await state.set_state(SheetStates.waiting_for_files)
    await state.update_data(upload_folder_id=folder_id, upload_folder_name=folder_name)
    await callback.message.edit_text(
        f"Папка: «{folder_name}»\nОтправьте файлы (документы)."
    )
    await callback.answer()


@router.callback_query(
    SheetStates.choosing_upload_folder, F.data == "create_upload_folder"
)
async def create_upload_folder_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SheetStates.entering_new_folder_name)
    await callback.message.edit_text("Введите название новой папки:")
    await callback.answer()


@router.message(SheetStates.entering_new_folder_name, F.text)
async def create_upload_folder_finish(
    message: Message,
    state: FSMContext,
    drive: DriveService,
    root_folder_id: str,
):
    folder_name = message.text.strip()
    if not folder_name:
        await message.answer("Название не может быть пустым. Попробуйте ещё раз.")
        return

    folder = drive.create_folder(folder_name, root_folder_id)
    await state.set_state(SheetStates.waiting_for_files)
    await state.update_data(
        upload_folder_id=folder["id"], upload_folder_name=folder["name"]
    )
    await message.answer(
        f"Папка «{folder['name']}» создана.\nОтправьте файлы (документы)."
    )


@router.message(SheetStates.waiting_for_files, F.document)
async def receive_file(message: Message, state: FSMContext):
    doc = message.document
    original_name = doc.file_name or "file"
    ext = os.path.splitext(original_name)[1]

    data = await state.get_data()
    folder_name = data.get("upload_folder_name", "")
    suggested_name = f"{folder_name}{ext}" if folder_name else original_name

    await state.update_data(
        pending_file_id=doc.file_id,
        pending_original_name=original_name,
        pending_suggested_name=suggested_name,
    )
    await state.set_state(SheetStates.confirming_filename)
    await message.answer(
        f"Имя файла: «{suggested_name}»",
        reply_markup=get_confirm_filename_keyboard(),
    )


@router.callback_query(SheetStates.confirming_filename, F.data == "confirm_filename")
async def confirm_filename(
    callback: CallbackQuery,
    state: FSMContext,
    drive: DriveService,
    bot=None,
):
    data = await state.get_data()
    filename = data["pending_suggested_name"]
    await _do_upload(callback, state, drive, filename)


@router.callback_query(SheetStates.confirming_filename, F.data == "rename_filename")
async def rename_filename(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите новое имя файла:")
    await callback.answer()


@router.message(SheetStates.confirming_filename, F.text)
async def receive_new_filename(
    message: Message,
    state: FSMContext,
    drive: DriveService,
):
    new_name = message.text.strip()
    if not new_name:
        await message.answer("Имя не может быть пустым. Попробуйте ещё раз.")
        return

    data = await state.get_data()
    original_name = data.get("pending_original_name", "")
    ext = os.path.splitext(original_name)[1]
    if ext and not os.path.splitext(new_name)[1]:
        new_name += ext

    await _do_upload_from_message(message, state, drive, new_name)


async def _do_upload(
    callback: CallbackQuery,
    state: FSMContext,
    drive: DriveService,
    filename: str,
):
    data = await state.get_data()
    file_id = data["pending_file_id"]
    folder_id = data["upload_folder_id"]

    file = await callback.bot.download(file_id)
    content = file.read()
    drive.upload_file(content, filename, folder_id)

    await state.set_state(SheetStates.waiting_for_files)
    await callback.message.edit_text(f"Файл «{filename}» загружен!")
    await callback.message.answer(
        "Отправьте ещё файл или нажмите «Готово».",
        reply_markup=get_more_files_keyboard(),
    )
    await callback.answer()


async def _do_upload_from_message(
    message: Message,
    state: FSMContext,
    drive: DriveService,
    filename: str,
):
    data = await state.get_data()
    file_id = data["pending_file_id"]
    folder_id = data["upload_folder_id"]

    file = await message.bot.download(file_id)
    content = file.read()
    drive.upload_file(content, filename, folder_id)

    await state.set_state(SheetStates.waiting_for_files)
    await message.answer(f"Файл «{filename}» загружен!")
    await message.answer(
        "Отправьте ещё файл или нажмите «Готово».",
        reply_markup=get_more_files_keyboard(),
    )


@router.callback_query(SheetStates.waiting_for_files, F.data == "upload_more")
async def upload_more(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отправьте файл (документ).")
    await callback.answer()


@router.callback_query(SheetStates.waiting_for_files, F.data == "upload_done")
async def upload_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    folder_id = data.get("upload_folder_id", "")
    folder_name = data.get("upload_folder_name", "")

    link = DriveService.get_folder_link(folder_id)
    await state.clear()
    await callback.message.edit_text(
        f'Готово! Папка <a href="{link}">{folder_name}</a>',
        parse_mode="HTML",
    )
    await callback.message.answer("Что дальше?", reply_markup=get_start_keyboard())
    await callback.answer()

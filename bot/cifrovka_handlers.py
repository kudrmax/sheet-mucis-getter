from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.keyboards import (
    CIFROVKI,
    get_cifrovka_actions_keyboard,
    get_cifrovka_delete_confirm_keyboard,
    get_cifrovka_folder_keyboard,
    get_cifrovka_versions_keyboard,
    get_start_keyboard,
)
from services.cifrovka_service import CifrovkaService
from services.drive_service import DriveService

router = Router()

MAX_MESSAGE_LEN = 4000


class CifrovkaStates(StatesGroup):
    selecting_folder = State()
    viewing = State()
    viewing_versions = State()
    entering_content = State()
    entering_note = State()
    editing_content = State()
    confirm_delete = State()


async def _send_long_text(message: Message, text: str) -> None:
    while text:
        chunk = text[:MAX_MESSAGE_LEN]
        text = text[MAX_MESSAGE_LEN:]
        await message.answer(chunk)


async def _show_latest(message: Message, state: FSMContext, cifrovka_service: CifrovkaService):
    data = await state.get_data()
    folder_id = data["cif_folder_id"]
    folder_name = data["cif_folder_name"]

    latest = cifrovka_service.get_latest_version(folder_id, folder_name)
    await state.set_state(CifrovkaStates.viewing)

    if latest:
        header = f"Цифровка «{folder_name}» (v{latest.version})"
        if latest.note:
            header += f"\nЗаметка: {latest.note}"
        await message.answer(header, reply_markup=get_cifrovka_actions_keyboard(True))
        await _send_long_text(message, latest.content)
    else:
        await message.answer(
            f"Цифровка для «{folder_name}» не найдена.",
            reply_markup=get_cifrovka_actions_keyboard(False),
        )


# ── Entry point ──


@router.message(F.text == CIFROVKI)
async def cifrovki_start(
    message: Message, state: FSMContext, drive: DriveService, root_folder_id: str,
):
    folders = drive.list_folders(root_folder_id)
    if not folders:
        await message.answer("Папки не найдены.", reply_markup=get_start_keyboard())
        return

    await state.set_state(CifrovkaStates.selecting_folder)
    await state.update_data(cif_folders=folders)
    await message.answer(
        "Выберите произведение:",
        reply_markup=get_cifrovka_folder_keyboard(folders),
    )


# ── Folder selection ──


@router.callback_query(CifrovkaStates.selecting_folder, F.data.startswith("cif_f:"))
async def select_folder(
    callback: CallbackQuery, state: FSMContext, cifrovka_service: CifrovkaService,
):
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    folders = data["cif_folders"]

    if idx < 0 or idx >= len(folders):
        await callback.answer("Неверный выбор", show_alert=True)
        return

    folder = folders[idx]
    await state.update_data(cif_folder_id=folder["id"], cif_folder_name=folder["name"])
    await callback.answer()
    await callback.message.edit_text(f"Произведение: «{folder['name']}»")
    await _show_latest(callback.message, state, cifrovka_service)


@router.callback_query(CifrovkaStates.selecting_folder, F.data == "cif_back")
async def back_from_folders(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Главное меню")
    await callback.message.answer("Что дальше?", reply_markup=get_start_keyboard())
    await callback.answer()


# ── Viewing actions ──


@router.callback_query(CifrovkaStates.viewing, F.data == "cif_versions")
async def show_versions(
    callback: CallbackQuery, state: FSMContext, cifrovka_service: CifrovkaService,
):
    data = await state.get_data()
    versions = cifrovka_service.get_versions(data["cif_folder_id"], data["cif_folder_name"])

    if not versions:
        await callback.answer("Нет версий", show_alert=True)
        return

    await state.set_state(CifrovkaStates.viewing_versions)
    await callback.message.edit_text(
        "Все версии:", reply_markup=get_cifrovka_versions_keyboard(versions),
    )
    await callback.answer()


@router.callback_query(CifrovkaStates.viewing, F.data == "cif_new")
async def new_version_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CifrovkaStates.entering_content)
    await callback.message.edit_text("Отправьте текст цифровки:")
    await callback.answer()


@router.callback_query(CifrovkaStates.viewing, F.data == "cif_edit")
async def edit_version_start(
    callback: CallbackQuery, state: FSMContext, cifrovka_service: CifrovkaService,
):
    data = await state.get_data()
    latest = cifrovka_service.get_latest_version(data["cif_folder_id"], data["cif_folder_name"])
    if not latest:
        await callback.answer("Нет версии для редактирования", show_alert=True)
        return

    await state.set_state(CifrovkaStates.editing_content)
    await state.update_data(cif_edit_version=latest.version)
    await callback.message.edit_text(f"Отправьте новый текст (v{latest.version}):")
    await callback.answer()


@router.callback_query(CifrovkaStates.viewing, F.data == "cif_delete")
async def delete_version_start(
    callback: CallbackQuery, state: FSMContext, cifrovka_service: CifrovkaService,
):
    data = await state.get_data()
    latest = cifrovka_service.get_latest_version(data["cif_folder_id"], data["cif_folder_name"])
    if not latest:
        await callback.answer("Нет версии для удаления", show_alert=True)
        return

    await state.set_state(CifrovkaStates.confirm_delete)
    await state.update_data(cif_delete_version=latest.version)
    await callback.message.edit_text(
        f"Удалить v{latest.version}?",
        reply_markup=get_cifrovka_delete_confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(CifrovkaStates.viewing, F.data == "cif_back")
async def back_from_viewing(
    callback: CallbackQuery, state: FSMContext, drive: DriveService, root_folder_id: str,
):
    folders = drive.list_folders(root_folder_id)
    await state.set_state(CifrovkaStates.selecting_folder)
    await state.update_data(cif_folders=folders)
    await callback.message.edit_text(
        "Выберите произведение:",
        reply_markup=get_cifrovka_folder_keyboard(folders),
    )
    await callback.answer()


# ── Viewing versions ──


@router.callback_query(CifrovkaStates.viewing_versions, F.data.startswith("cif_v:"))
async def show_single_version(
    callback: CallbackQuery, state: FSMContext, cifrovka_service: CifrovkaService,
):
    ver = int(callback.data.split(":")[1])
    data = await state.get_data()
    versions = cifrovka_service.get_versions(data["cif_folder_id"], data["cif_folder_name"])
    target = next((v for v in versions if v.version == ver), None)

    if not target:
        await callback.answer("Версия не найдена", show_alert=True)
        return

    header = f"v{target.version} ({target.created_at[:10]}) — {target.author}"
    if target.note:
        header += f"\nЗаметка: {target.note}"

    await callback.message.edit_text(header)
    await _send_long_text(callback.message, target.content)

    # Show versions list again
    await callback.message.answer(
        "Все версии:", reply_markup=get_cifrovka_versions_keyboard(versions),
    )
    await callback.answer()


@router.callback_query(CifrovkaStates.viewing_versions, F.data == "cif_back_view")
async def back_to_viewing(
    callback: CallbackQuery, state: FSMContext, cifrovka_service: CifrovkaService,
):
    await callback.message.edit_text("Загрузка...")
    await callback.answer()
    await _show_latest(callback.message, state, cifrovka_service)


# ── Create new version ──


@router.message(CifrovkaStates.entering_content, F.text)
async def receive_content(message: Message, state: FSMContext):
    await state.update_data(cif_new_content=message.text)
    await state.set_state(CifrovkaStates.entering_note)
    await message.answer("Заметка? (отправьте текст или /skip)")


@router.message(CifrovkaStates.entering_note, F.text)
async def receive_note(
    message: Message, state: FSMContext, cifrovka_service: CifrovkaService,
):
    note = "" if message.text.strip() == "/skip" else message.text.strip()
    data = await state.get_data()

    entry = cifrovka_service.create_version(
        folder_id=data["cif_folder_id"],
        folder_name=data["cif_folder_name"],
        content=data["cif_new_content"],
        author=message.from_user.full_name,
        note=note,
    )
    await message.answer(f"Сохранено: v{entry.version}")
    await _show_latest(message, state, cifrovka_service)


# ── Edit version ──


@router.message(CifrovkaStates.editing_content, F.text)
async def receive_edit(
    message: Message, state: FSMContext, cifrovka_service: CifrovkaService,
):
    data = await state.get_data()
    result = cifrovka_service.edit_version(
        folder_id=data["cif_folder_id"],
        version=data["cif_edit_version"],
        content=message.text,
        note="",
        author=message.from_user.full_name,
    )
    if result:
        await message.answer(f"v{result.version} обновлена")
    else:
        await message.answer("Версия не найдена")
    await _show_latest(message, state, cifrovka_service)


# ── Delete version ──


@router.callback_query(CifrovkaStates.confirm_delete, F.data == "cif_del_yes")
async def confirm_delete(
    callback: CallbackQuery, state: FSMContext, cifrovka_service: CifrovkaService,
):
    data = await state.get_data()
    ok = cifrovka_service.delete_version(data["cif_folder_id"], data["cif_delete_version"])

    if ok:
        await callback.message.edit_text(f"v{data['cif_delete_version']} удалена")
    else:
        await callback.message.edit_text("Версия не найдена")

    await callback.answer()
    await _show_latest(callback.message, state, cifrovka_service)


@router.callback_query(CifrovkaStates.confirm_delete, F.data == "cif_del_no")
async def cancel_delete(
    callback: CallbackQuery, state: FSMContext, cifrovka_service: CifrovkaService,
):
    await callback.message.edit_text("Удаление отменено")
    await callback.answer()
    await _show_latest(callback.message, state, cifrovka_service)

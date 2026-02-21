from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.keyboards import (
    FORMS,
    get_form_delete_confirm_keyboard,
    get_form_empty_keyboard,
    get_form_folder_keyboard,
    get_form_view_keyboard,
    get_start_keyboard,
)
from services.form_service import FormService
from services.drive_service import DriveService

router = Router()

MAX_MESSAGE_LEN = 4096


class FormStates(StatesGroup):
    selecting_folder = State()
    viewing = State()
    entering_content = State()
    entering_note = State()
    editing_content = State()
    confirm_delete = State()


def _format_form_text(folder_name: str, form) -> str:
    text = f"\U0001f353 {folder_name}\n\n{form.content}"
    if form.note:
        text += f"\n\n\U0001f4dd {form.note}"
    return text


def _resolve_idx(data: dict, total: int) -> int:
    idx = data.get("form_version_idx")
    if idx is None:
        idx = total - 1  # last = pinned or latest version
    return max(0, min(idx, total - 1))


async def _show_version(
    message: Message,
    state: FSMContext,
    form_service: FormService,
    *,
    edit: bool = True,
):
    data = await state.get_data()
    folder_id = data["form_folder_id"]
    folder_name = data["form_folder_name"]

    versions = form_service.get_versions(folder_id, folder_name)
    await state.set_state(FormStates.viewing)

    if not versions:
        text = f"\U0001f353 {folder_name}\n\nФорма не найдена."
        kb = get_form_empty_keyboard()
        if edit:
            await message.edit_text(text, reply_markup=kb)
        else:
            await message.answer(text, reply_markup=kb)
        return

    idx = _resolve_idx(data, len(versions))
    await state.update_data(form_version_idx=idx)

    form = versions[idx]
    text = _format_form_text(folder_name, form)

    if len(text) > MAX_MESSAGE_LEN:
        text = text[: MAX_MESSAGE_LEN - 3] + "..."

    kb = get_form_view_keyboard(idx, len(versions), is_pinned=form.pinned)
    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


# ── Entry point ──


@router.message(F.text == FORMS)
async def forms_start(
    message: Message, state: FSMContext, drive: DriveService, root_folder_id: str,
):
    folders = drive.list_folders(root_folder_id)
    if not folders:
        await message.answer("Папки не найдены.", reply_markup=get_start_keyboard())
        return

    await state.set_state(FormStates.selecting_folder)
    await state.update_data(form_folders=folders)
    await message.answer(
        "Выберите произведение:",
        reply_markup=get_form_folder_keyboard(folders),
    )


# ── Folder selection ──


@router.callback_query(FormStates.selecting_folder, F.data.startswith("frm_f:"))
async def select_folder(
    callback: CallbackQuery, state: FSMContext, form_service: FormService,
):
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    folders = data["form_folders"]

    if idx < 0 or idx >= len(folders):
        await callback.answer("Неверный выбор", show_alert=True)
        return

    folder = folders[idx]
    await state.update_data(
        form_folder_id=folder["id"],
        form_folder_name=folder["name"],
        form_version_idx=None,
    )
    await callback.answer()
    await _show_version(callback.message, state, form_service, edit=True)


@router.callback_query(FormStates.selecting_folder, F.data == "frm_back")
async def back_from_folders(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Что дальше?")
    await callback.message.answer("Выберите действие:", reply_markup=get_start_keyboard())
    await callback.answer()


# ── Navigation ──


@router.callback_query(FormStates.viewing, F.data == "frm_prev")
async def prev_version(
    callback: CallbackQuery, state: FSMContext, form_service: FormService,
):
    data = await state.get_data()
    idx = data.get("form_version_idx", 0)
    await state.update_data(form_version_idx=max(0, idx - 1))
    await callback.answer()
    await _show_version(callback.message, state, form_service, edit=True)


@router.callback_query(FormStates.viewing, F.data == "frm_next")
async def next_version(
    callback: CallbackQuery, state: FSMContext, form_service: FormService,
):
    data = await state.get_data()
    idx = data.get("form_version_idx", 0)
    await state.update_data(form_version_idx=idx + 1)
    await callback.answer()
    await _show_version(callback.message, state, form_service, edit=True)


@router.callback_query(FormStates.viewing, F.data == "frm_noop")
async def noop(callback: CallbackQuery):
    await callback.answer()


# ── Actions ──


@router.callback_query(FormStates.viewing, F.data == "frm_pin")
async def toggle_pin(
    callback: CallbackQuery, state: FSMContext, form_service: FormService,
):
    data = await state.get_data()
    versions = form_service.get_versions(data["form_folder_id"], data["form_folder_name"])
    if not versions:
        await callback.answer()
        return

    idx = _resolve_idx(data, len(versions))
    form = versions[idx]
    new_state = form_service.toggle_pin(data["form_folder_id"], form.version)

    await state.update_data(form_version_idx=None)
    await callback.answer("\U0001f4cc Закреплено" if new_state else "\U0001f4cd Откреплено")
    await _show_version(callback.message, state, form_service, edit=True)


@router.callback_query(FormStates.viewing, F.data == "frm_new")
async def new_version_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FormStates.entering_content)
    await callback.message.edit_text("Отправьте текст формы:")
    await callback.answer()


@router.callback_query(FormStates.viewing, F.data == "frm_edit")
async def edit_version_start(
    callback: CallbackQuery, state: FSMContext, form_service: FormService,
):
    data = await state.get_data()
    versions = form_service.get_versions(data["form_folder_id"], data["form_folder_name"])
    if not versions:
        await callback.answer("Нет версии для редактирования", show_alert=True)
        return

    idx = _resolve_idx(data, len(versions))
    form = versions[idx]

    await state.set_state(FormStates.editing_content)
    await state.update_data(form_edit_version=form.version)
    await callback.message.edit_text(f"Отправьте новый текст (v{form.version}):")
    await callback.answer()


@router.callback_query(FormStates.viewing, F.data == "frm_delete")
async def delete_version_start(
    callback: CallbackQuery, state: FSMContext, form_service: FormService,
):
    data = await state.get_data()
    versions = form_service.get_versions(data["form_folder_id"], data["form_folder_name"])
    if not versions:
        await callback.answer("Нет версии для удаления", show_alert=True)
        return

    idx = _resolve_idx(data, len(versions))
    form = versions[idx]

    await state.set_state(FormStates.confirm_delete)
    await state.update_data(form_delete_version=form.version)
    await callback.message.edit_text(
        f"Удалить v{form.version}?",
        reply_markup=get_form_delete_confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(FormStates.viewing, F.data == "frm_back")
async def back_from_viewing(
    callback: CallbackQuery, state: FSMContext, drive: DriveService, root_folder_id: str,
):
    folders = drive.list_folders(root_folder_id)
    await state.set_state(FormStates.selecting_folder)
    await state.update_data(form_folders=folders)
    await callback.message.edit_text(
        "Выберите произведение:",
        reply_markup=get_form_folder_keyboard(folders),
    )
    await callback.answer()


# ── Create new version ──


@router.message(FormStates.entering_content, F.text)
async def receive_content(message: Message, state: FSMContext):
    await state.update_data(form_new_content=message.text)
    await state.set_state(FormStates.entering_note)
    await message.answer("Заметка? (отправьте текст или /skip)")


@router.message(FormStates.entering_note, F.text)
async def receive_note(
    message: Message, state: FSMContext, form_service: FormService,
):
    note = "" if message.text.strip() == "/skip" else message.text.strip()
    data = await state.get_data()

    entry = form_service.create_version(
        folder_id=data["form_folder_id"],
        folder_name=data["form_folder_name"],
        content=data["form_new_content"],
        author=message.from_user.full_name,
        note=note,
    )

    await state.update_data(form_version_idx=None)
    await message.answer(f"Сохранено: v{entry.version}")
    await _show_version(message, state, form_service, edit=False)


# ── Edit version ──


@router.message(FormStates.editing_content, F.text)
async def receive_edit(
    message: Message, state: FSMContext, form_service: FormService,
):
    data = await state.get_data()
    result = form_service.edit_version(
        folder_id=data["form_folder_id"],
        version=data["form_edit_version"],
        content=message.text,
        note="",
        author=message.from_user.full_name,
    )
    if result:
        await message.answer(f"v{result.version} обновлена")
    else:
        await message.answer("Версия не найдена")
    await _show_version(message, state, form_service, edit=False)


# ── Delete version ──


@router.callback_query(FormStates.confirm_delete, F.data == "frm_del_yes")
async def confirm_delete(
    callback: CallbackQuery, state: FSMContext, form_service: FormService,
):
    data = await state.get_data()
    ver = data["form_delete_version"]
    ok = form_service.delete_version(data["form_folder_id"], ver)

    await state.update_data(form_version_idx=None)

    if ok:
        await callback.answer(f"v{ver} удалена")
    else:
        await callback.answer("Версия не найдена", show_alert=True)

    await _show_version(callback.message, state, form_service, edit=True)


@router.callback_query(FormStates.confirm_delete, F.data == "frm_del_no")
async def cancel_delete(
    callback: CallbackQuery, state: FSMContext, form_service: FormService,
):
    await callback.answer("Отменено")
    await _show_version(callback.message, state, form_service, edit=True)

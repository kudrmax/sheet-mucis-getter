from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

CHOOSE_SHEETS = "Выбрать ноты"
UPLOAD_SHEETS = "Загрузить ноты"


def get_start_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=CHOOSE_SHEETS), KeyboardButton(text=UPLOAD_SHEETS)]
        ],
        resize_keyboard=True,
    )


def get_folders_inline_keyboard(
    folders: list[dict], selected_ids: set[str]
) -> InlineKeyboardMarkup:
    buttons = []
    for folder in folders:
        mark = "\u2705" if folder["id"] in selected_ids else "\u2b1c"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {folder['name']}",
                    callback_data=f"folder_toggle:{folder['id']}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(text="Выбрать все", callback_data="select_all"),
            InlineKeyboardButton(
                text="Скачать выбранные", callback_data="download_selected"
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_upload_folders_inline_keyboard(
    folders: list[dict],
) -> InlineKeyboardMarkup:
    buttons = []
    for folder in folders:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=folder["name"],
                    callback_data=f"upload_folder:{folder['id']}:{folder['name']}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="Создать папку", callback_data="create_upload_folder"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirm_filename_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить", callback_data="confirm_filename"
                ),
                InlineKeyboardButton(
                    text="Переименовать", callback_data="rename_filename"
                ),
            ]
        ]
    )


def get_more_files_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Загрузить ещё", callback_data="upload_more"
                ),
                InlineKeyboardButton(text="Готово", callback_data="upload_done"),
            ]
        ]
    )

"""Шаблоны ошибок в коде"""
from enum import Enum


class Error(Enum):
    """
    Response-сообщения о типовых ошибках
    """
    USER_NOT_AUTHENTICATED = {
        'Status': False,
        'Error': 'Необходима авторизация'
    }
    NOT_REQUIRED_ARGS = {
        'Status': False,
        'Error': 'Не указаны все необходимые аргументы'
    }
    AUTH_FAILED = {
        'Status': False,
        'Error': 'Не удалось авторизовать пользователя'
    }
    BASKET_HAS_GOOD_FROM_DIFFERENT_SHOP = {
        'Status': False,
        'Error': 'В корзине находится товар из другого магазина'
    }
    BASKET_IS_EMPTY = {
        'Status': False,
        'Error': 'В корзине нет выбранных товаров'
    }
    BUYER_ONLY = {
        'Status': False,
        'Error': 'Оставить оценку и отзыв можно только на приобретенный в магазине товар'
    }
    CONTACT_NOT_EXIST = {
        'Status': False,
        'Error': 'Контакт не существует или адрес не принадлежит контакту пользователя'
    }
    CONTACTS_EXCEEDING = {
        'Status': False,
        'Error': 'Нельзя добавить пользователю более 5 контактов'
    }
    CONTACTS_NOT_EXIST = {
        'Status': False,
        'Error': 'Адресов с такими id не существует, адрес не принадлежит контакту пользователя или у пользователя нет'
                 ' контактных данных'
    }
    CONTACT_WRONG = {
        'Status': False,
        'Error': 'Некорректное значение аргумента contact'
    }
    DATE_WRONG = {
        'Status': False,
        'Error': 'Некорректное значение параметра даты'
    }
    DELETE_CONTACT_WRONG = {
        'Status': False,
        'Error': 'Некорректное значение аргумента delete_contact'
    }
    DELIVERY_TIME_WRONG = {
        'Status': False,
        'Error': 'Некорректное значение аргумента delivery_time'
    }
    EMAIL_CHANGE_FAILED = {
        'Status': False,
        'Error': 'Не удалось доставить письмо на email для активации. Email не был изменен'
    }
    EMAIL_OR_TOKEN_WRONG = {
        'Status': False,
        'Error': 'Некорректное значение аргумента email или token'
    }
    EMAIL_WRONG = {
        'Status': False,
        'Error': 'Некорректное значение аргумента email'
    }
    FILE_INCORRECT = {
        'Status': False,
        'Error': 'Некорректный формат файла'
    }
    IDS_NOT_EXIST = {
        'Status': False,
        'Error': 'Нет изображений товаров с таким/такими id или вы пытаетесь удалить главное изображение'
    }
    ID_NOT_INT = {
        'Status': False,
        'Error': 'Аргумент "id" должен быть числом'
    }
    ID_OR_QUANTITY_WRONG_TYPE = {
        'Status': False,
        'Error': 'Некорректное значение id продукта или количества'
    }
    IDS_WRONG_TYPE = {
        'Status': False,
        'Error': 'Некорректное значение аргумента ids'
    }
    IS_MAIN_WRONG_TYPE = {
        'Status': False,
        'Error': 'Некорректное значение аргумента is_main'
    }
    ORDER_NOT_EXIST = {
        'Status': False,
        'Error': 'Заказ не существует'
    }
    PRODUCT_ID_WRONG_TYPE = {
        'Status': False,
        'Error': 'Некорректное значение аргумента product_id'
    }
    PRODUCT_INFO_NOT_EXISTS = {
        'Status': False,
        'Error': 'Товара с таким id нет в магазине'
    }
    PRODUCT_WRONG_TYPE = {
        'Status': False,
        'Error': 'Некорректное значение аргумента product'
    }
    RATING_DUPLICATE = {
        'Status': False,
        'Error': 'Вы уже оставляли оценку этому товару'
    }
    RATING_WRONG_TYPE_OR_VALUE = {
        'Status': False,
        'Error': 'Некорректное значение аргумента rating'
    }
    SHOP_USER_NOT_RELATED = {
        'Status': False,
        'Error': 'Пользователь закреплен за другим магазином'
    }
    STATE_WRONG = {
        'Status': False,
        'Error': 'Указано некорректное значение аргумента state'
    }
    URL_NOT_SPECIFIED = {
        'Status': False,
        'Error': 'Необходимо указать url магазина'
    }
    USER_TYPE_NOT_SHOP = {
        'Status': False,
        'Error': 'Функционал доступен только менеджеру магазина'
    }
    USER_HAS_NO_SHOP = {
        'Status': False,
        'Error': 'У пользователя нет закрепленного магазина'
    }


class ValidateError(Enum):
    """
    Ошибки валидации данных
    """
    ANOTHER_USER_CONTACT = 'Контакт не указан или не принадлежит пользователю'
    CITY_IS_INCORRECT = 'Некорректное название города'
    CONTACTS_EXCEEDING = 'Нельзя добавить пользователю более 5 контактов'
    DELIVERY_DATE_WRONG = 'Необходимо указать дату доставки'
    DELIVERY_TIME_WRONG = 'Необходимо указать время доставки'
    DIFFERENT_SHOPS = 'Нельзя добавить в один заказ товары из разных магазинов'
    DUPLICATE_BASKET = 'Нельзя создать вторую корзину'
    EMAIL_FAILED = 'Не удалось доставить письмо с изменением статуса заказа на электронную почту'
    EMAIL_NOT_UNIQUE = 'Пользователь с таким email уже существует'
    ICON_EXCEEDING = 'Основная иконка может быть только одна'
    ICON_IS_EMPTY = 'Выберите основную иконку'
    NAME_REQUIRED = 'Необходимо указать имя и фамилию пользователя'
    ORDER_IS_EMPTY = 'Невозможно сохранить пустой заказ/корзину'
    PHONE_IS_INCORRECT = 'Некорректный номер телефона'
    RECIPIENT_IS_EMPTY = 'Необходимо указать получателя доставки'
    STREET_IS_INCORRECT = 'Некорректное название улицы'
    USER_HAS_ANOTHER_SHOP = 'Пользователь закреплен за другим магазином'
    USER_INACTIVE = 'Пользователь неактивен'
    USER_NOT_BUYER = 'Указанный пользователь не является приобретателем товара'
    USER_WRONG_TYPE = 'Пользователь должен иметь роль менеджера'

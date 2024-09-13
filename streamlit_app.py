import streamlit as st
import pandas as pd
import sqlite3
import random
import string
from datetime import datetime, timedelta
import pytz

# Подключение к базе данных SQLite3
conn = sqlite3.connect('auth_system.db', check_same_thread=False)
c = conn.cursor()

# Создание таблиц, если они не существуют
c.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    token TEXT NOT NULL
)
''')
conn.commit()

c.execute('''
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    purchase_price REAL NOT NULL,
    sale_price REAL NOT NULL,
    quantity_in_stock INTEGER NOT NULL DEFAULT 0,
    user_id INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
''')
conn.commit()

c.execute('''
CREATE TABLE IF NOT EXISTS cart (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    UNIQUE(product_id)
)
''')
conn.commit()

c.execute('''
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id TEXT NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    sale_date TIMESTAMP NOT NULL,
    total_amount REAL NOT NULL,
    FOREIGN KEY(product_id) REFERENCES products(id)
)
''')
conn.commit()

# Функция для генерации случайного 13-значного токена
def generate_token():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=13))

# Функция для получения идентификатора пользователя по токену
def get_user_id_by_token(token):
    c.execute("SELECT id FROM users WHERE token=?", (token,))
    user = c.fetchone()
    return user[0] if user else None

# Функция для получения товаров из корзины
def get_cart_summary(user_id):
    c.execute('''
    SELECT p.name, c.quantity, p.sale_price, c.quantity * p.sale_price
    FROM cart c
    JOIN products p ON c.product_id = p.id
    WHERE p.user_id = ?
    ''', (user_id,))
    items = c.fetchall()
    total_quantity = sum(item[1] for item in items)
    total_price = sum(item[3] for item in items)
    return items, total_quantity, total_price

# Функция для добавления продажи в отчет
def record_sales():
    sales_details = []
    sale_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))  # Уникальный идентификатор сделки
    sale_date = datetime.now(pytz.timezone('Asia/Bishkek')).strftime('%Y-%m-%d %H:%M:%S')
    
    c.execute('SELECT product_id, quantity FROM cart')
    cart_items = c.fetchall()
    
    total_amount = 0.0
    for product_id, quantity in cart_items:
        # Получение цены за единицу товара
        c.execute('SELECT sale_price FROM products WHERE id=?', (product_id,))
        sale_price = c.fetchone()[0]
        
        # Расчет общей суммы для этого товара
        amount = quantity * sale_price
        total_amount += amount
        
        c.execute('''
        INSERT INTO sales (sale_id, product_id, quantity, sale_date, total_amount)
        VALUES (?, ?, ?, ?, ?)
        ''', (sale_id, product_id, quantity, sale_date, amount))
        sales_details.append((product_id, quantity, amount, sale_date))
        
    c.execute('DELETE FROM cart')
    conn.commit()
    return sales_details, sale_id, total_amount

# Функция для генерации отчета за месяц
def generate_monthly_report(user_id):
    start_date = (datetime.now().replace(day=1)).strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=31)).replace(day=1).strftime('%Y-%m-%d')

    c.execute('''
    SELECT p.name, SUM(s.quantity) AS total_quantity, p.sale_price, SUM(s.quantity) * p.sale_price AS total_sales, 
           SUM(s.quantity) * (p.sale_price - p.purchase_price) AS profit
    FROM sales s
    JOIN products p ON s.product_id = p.id
    WHERE s.sale_date BETWEEN ? AND ? AND p.user_id = ?
    GROUP BY p.id
    ''', (start_date, end_date, user_id))
    
    sales_data = c.fetchall()

    total_sales = sum(item[3] for item in sales_data)
    total_profit = sum(item[4] for item in sales_data)
    
    return sales_data, total_sales, total_profit


# Функция для получения всех сделок
def get_all_sales(user_id):
    c.execute('''
    SELECT DISTINCT sale_id, sale_date, SUM(total_amount) AS total_amount
    FROM sales s
    JOIN products p ON s.product_id = p.id
    WHERE p.user_id = ?
    GROUP BY sale_id, sale_date
    ORDER BY sale_date DESC
    ''', (user_id,))
    sales_data = c.fetchall()
    return sales_data


# Функция для получения всех подробностей сделок
def get_sale_details(sale_id):
    c.execute('''
    SELECT p.name, s.quantity, p.sale_price, s.sale_date
    FROM sales s
    JOIN products p ON s.product_id = p.id
    WHERE s.sale_id = ?
    ''', (sale_id,))
    sale_details = c.fetchall()
    return sale_details

# Страница регистрации
def register():
    st.title('Регистрация')
    username = st.text_input("Введите ваше имя пользователя")
    admin_password = st.text_input("Введите пароль администратора", type="password")

    if st.button("Зарегистрироваться"):
        if admin_password == "morshenfullsumflpol":
            token = generate_token()
            try:
                c.execute("INSERT INTO users (username, token) VALUES (?, ?)", (username, token))
                conn.commit()
                st.success(f"Регистрация успешна! Ваш токен: {token}")
            except sqlite3.IntegrityError:
                st.error("Это имя пользователя уже занято. Попробуйте другое.")
        else:
            st.error("Неверный пароль администратора!")

# Страница авторизации
def login():
    st.title('Авторизация')
    token_input = st.text_input("Введите ваш токен")

    if st.button("Войти"):
        user_id = get_user_id_by_token(token_input)
        if user_id:
            st.session_state.logged_in = True  # Устанавливаем состояние авторизации
            st.session_state.username = token_input
            st.session_state.user_id = user_id
            st.success("Добро пожаловать!")
        else:
            st.error("Неверный токен!")

# Форма добавления товара
def add_product():
    st.title("Добавление товара")
    product_name = st.text_input("Название товара").strip().lower()  # Преобразование в нижний регистр
    product_description = st.text_area("Описание товара")
    purchase_price = st.number_input("Приходная цена", min_value=0.0, step=0.01)  # Запрос приходной цены
    sale_price = st.number_input("Отпускная цена", min_value=0.0, step=0.01)      # Запрос отпускной цены
    product_quantity = st.number_input("Количество на складе", min_value=0, step=1)

    if st.button("Добавить товар"):
        if product_name and sale_price:
            c.execute("INSERT INTO products (name, description, purchase_price, sale_price, quantity_in_stock, user_id) VALUES (?, ?, ?, ?, ?, ?)", 
                      (product_name, product_description, purchase_price, sale_price, product_quantity, st.session_state.user_id))
            conn.commit()
            st.success("Товар успешно добавлен!")
        else:
            st.error("Пожалуйста, введите все обязательные данные.")

# Форма редактирования и удаления товара
def edit_products():
    st.title("Редактирование товара")
    products = c.execute("SELECT id, name, description, purchase_price, sale_price, quantity_in_stock FROM products WHERE user_id=?", 
                         (st.session_state.user_id,)).fetchall()
    
    if products:
        product_names = [p[1] for p in products]
        product_id = st.selectbox("Выберите товар", product_names)
        product = next(p for p in products if p[1] == product_id)
        
        new_name = st.text_input("Новое название товара", product[1])
        new_description = st.text_area("Новое описание товара", product[2])
        new_purchase_price = st.number_input("Новая приходная цена", min_value=0.0, step=0.01, value=product[3])
        new_sale_price = st.number_input("Новая отпускная цена", min_value=0.0, step=0.01, value=product[4])
        new_quantity_in_stock = st.number_input("Новое количество на складе", min_value=0, step=1, value=product[5])
        
        if st.button("Сохранить изменения"):
            c.execute('''
            UPDATE products
            SET name = ?, description = ?, purchase_price = ?, sale_price = ?, quantity_in_stock = ?
            WHERE id = ?
            ''', (new_name, new_description, new_purchase_price, new_sale_price, new_quantity_in_stock, product[0]))
            conn.commit()
            st.success("Товар успешно обновлен!")

        if st.button("Удалить товар"):
            c.execute("DELETE FROM products WHERE id=?", (product[0],))
            conn.commit()
            st.success("Товар успешно удален!")

# Форма отпуска товара
def add_to_cart():
    st.title("Отпуск товара")
    products = c.execute("SELECT id, name, sale_price, quantity_in_stock FROM products WHERE user_id=?", 
                         (st.session_state.user_id,)).fetchall()
    search_term = st.text_input("Поиск товара").strip().lower()  # Преобразуем ввод в нижний регистр

    # Поиск товаров по ключевому слову (без учета регистра)
    c.execute("SELECT id, name, sale_price, quantity_in_stock FROM products WHERE user_id=? AND LOWER(name) LIKE ?", 
              (st.session_state.user_id, f"%{search_term}%"))
    products = c.fetchall()

    if products:
        for product in products:
            cols = st.columns(4)
            with cols[0]:
                st.write(product[1])  # Название товара
                st.write(f"**Отпускная цена**: {product[2]:.2f}")  # Показываем только отпускную цену
                st.write(f"**Остаток на складе**: {product[3]}")

            with cols[1]:
                quantity = st.number_input(f"Количество для '{product[1]}'", min_value=0, max_value=product[3], key=f"quantity_{product[0]}")
                
            with cols[2]:
                add_button = st.button(f"Добавить в корзину", key=f"add_{product[0]}")
                
                if add_button:
                    if quantity <= product[3]:
                        # Обработка добавления товара в корзину
                        c.execute('''
                        INSERT INTO cart (product_id, quantity) 
                        VALUES (?, ?)
                        ON CONFLICT(product_id) 
                        DO UPDATE SET quantity = quantity + excluded.quantity
                        ''', (product[0], quantity))

                        # Уменьшаем количество на складе
                        c.execute("UPDATE products SET quantity_in_stock = quantity_in_stock - ? WHERE id=?", 
                                  (quantity, product[0]))
                        conn.commit()
                        st.success(f"Товар '{product[1]}' успешно добавлен в корзину!")
                    else:
                        st.error(f"Недостаточное количество товара '{product[1]}' на складе!")

            with cols[3]:
                remove_button = st.button(f"Удалить из корзины", key=f"remove_{product[0]}")
                
                if remove_button:
                    if quantity > 0:
                        # Обработка удаления товара из корзины
                        current_quantity = c.execute("SELECT quantity FROM cart WHERE product_id=?", (product[0],)).fetchone()
                        if current_quantity:
                            new_quantity = current_quantity[0] - quantity
                            if new_quantity > 0:
                                c.execute('''
                                INSERT INTO cart (product_id, quantity) 
                                VALUES (?, ?)
                                ON CONFLICT(product_id) 
                                DO UPDATE SET quantity = excluded.quantity
                                ''', (product[0], new_quantity))
                            else:
                                c.execute("DELETE FROM cart WHERE product_id=?", (product[0],))

                            # Увеличиваем количество на складе
                            c.execute("UPDATE products SET quantity_in_stock = quantity_in_stock + ? WHERE id=?", 
                                      (quantity, product[0]))
                            conn.commit()
                            st.success(f"Товар '{product[1]}' успешно удалён из корзины!")
                        else:
                            st.error(f"Товар '{product[1]}' не найден в корзине.")
                    else:
                        st.error(f"Введите количество для удаления товара '{product[1]}'.")

        # Отображение состояния корзины
        st.subheader("Состояние корзины")
        items, total_quantity, total_price = get_cart_summary(st.session_state.user_id)
        
        if items:
            # Создание DataFrame для таблицы
            df = pd.DataFrame(items, columns=["Название", "Количество", "Цена за единицу", "Итого"])
            st.dataframe(df.style.format({"Цена за единицу": "{:.2f}", "Итого": "{:.2f}"}), use_container_width=True)
            
            st.write(f"Общее количество: {total_quantity}, Общая стоимость: {total_price:.2f}")
            
            # Добавляем кнопку "Пробить" для оформления продажи
            if st.button("Пробить"):
                sales_details, sale_id, total_amount = record_sales()
                if sales_details:
                    st.write("**Детали сделок:**")
                    sale_details_df = pd.DataFrame(sales_details, columns=["ID товара", "Количество", "Сумма", "Дата и время"])
                    st.dataframe(sale_details_df.style.format({"Сумма": "{:.2f}", "Дата и время": lambda x: pd.to_datetime(x).strftime('%d-%m-%Y %H:%M:%S')}), use_container_width=True)
                    st.write(f"**Общая сумма сделки:** {total_amount:.2f}")
                    st.success("Корзина успешно пробита! Все товары добавлены в отчет и корзина очищена.")
                
            # Кнопка для отображения сделок
            if st.button("Сделки"):
                sales_data = get_all_sales()
                if sales_data:
                    sale_ids = [sale[0] for sale in sales_data]
                    for sale_id, sale_date, total_amount in sales_data:
                        st.write(f"**Сделка ID:** {sale_id} ({sale_date}) - **Общая сумма:** {total_amount:.2f}")
                        sale_details = get_sale_details(sale_id)
                        if sale_details:
                            df_sales = pd.DataFrame(sale_details, columns=["Название товара", "Количество", "Цена за единицу", "Дата и время"])
                            st.dataframe(df_sales.style.format({"Дата и время": lambda x: pd.to_datetime(x).strftime('%d-%m-%Y %H:%M:%S')}), use_container_width=True)
                        else:
                            st.info("Нет деталей для отображения.")
                else:
                    st.info("Нет сделок для отображения.")
        else:
            st.info("Корзина пуста.")

# Страница отчета о продажах за месяц
def monthly_report():
    st.title("Отчет о продажах за месяц")
    sales_data, total_sales, total_profit = generate_monthly_report(st.session_state.user_id)
    if sales_data:
        # Создание DataFrame для отчета
        df = pd.DataFrame(sales_data, columns=["Название", "Общее количество", "Отпускная цена", "Общие продажи", "Прибыль"])
        st.write(f"**Отчет за {datetime.now().strftime('%B %Y')}**")
        st.dataframe(df.style.format({"Отпускная цена": "{:.2f}", "Общие продажи": "{:.2f}", "Прибыль": "{:.2f}"}), use_container_width=True)
        
        st.write(f"**Общая сумма продаж**: {total_sales:.2f}")
        st.write(f"**Общая сумма прибыли**: {total_profit:.2f}")
        
        # Кнопка для отображения сделок
        if st.button("Сделки"):
            sales_data = get_all_sales(st.session_state.user_id)
            if sales_data:
                sale_ids = [sale[0] for sale in sales_data]
                for sale_id, sale_date, total_amount in sales_data:
                    st.write(f"**Сделка ID:** {sale_id} ({sale_date}) - **Общая сумма:** {total_amount:.2f}")
                    sale_details = get_sale_details(sale_id)
                    if sale_details:
                        df_sales = pd.DataFrame(sale_details, columns=["Название товара", "Количество", "Цена за единицу", "Дата и время"])
                        st.dataframe(df_sales.style.format({"Дата и время": lambda x: pd.to_datetime(x).strftime('%d-%m-%Y %H:%M:%S')}), use_container_width=True)
                    else:
                        st.info("Нет деталей для отображения.")
            else:
                st.info("Нет сделок для отображения.")
    else:
        st.info("Нет данных о продажах за этот месяц.")

# Главная функция приложения
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if st.session_state.logged_in:
        st.sidebar.title(f"Привет, {st.session_state.username}!")
        option = st.sidebar.selectbox("Выберите действие", ["Добавить товар", "Отпуск товара", "Редактировать товары", "Отчет за месяц", "Выйти"])

        if option == "Добавить товар":
            add_product()
        elif option == "Отпуск товара":
            add_to_cart()
        elif option == "Редактировать товары":
            edit_products()
        elif option == "Отчет за месяц":
            monthly_report()
        elif option == "Выйти":
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.user_id = None
            st.success("Вы вышли из системы!")
    else:
        page = st.sidebar.selectbox("Выберите страницу", ["Авторизация", "Регистрация"])
        if page == "Регистрация":
            register()
        elif page == "Авторизация":
            login()

if __name__ == "__main__":
    main()

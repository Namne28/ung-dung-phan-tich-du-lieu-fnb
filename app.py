# pyrefly: ignore [missing-import]
import streamlit as st
import pandas as pd
# pyrefly: ignore [missing-import]
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import pyodbc
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="F&B Operations Dashboard", layout="wide")

# --- 1. KẾT NỐI SQL SERVER (HOẶC ĐỌC TỪ CSV NẾU LỖI) ---
@st.cache_data
def load_data():
    try:
        # CẤU HÌNH THÔNG TIN SQL SERVER CỦA BẠN Ở ĐÂY
        server = 'localhost' # Ví dụ: 'localhost\SQLEXPRESS'
        database = 'pizza'                      # Tên Database bạn đã tạo
        username = ''                             # Để trống nếu dùng Windows Authentication
        password = ''
        
        # Chuỗi kết nối Windows Authentication
        conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;'
        
        conn = pyodbc.connect(conn_str)
        st.sidebar.success("✅ Đã kết nối SQL Server thành công!")
        
        # Truy vấn gộp dữ liệu từ SQL Server
        query = """
        SELECT 
            o.date, o.time, 
            od.quantity, 
            p.price, p.size, 
            pt.name, pt.category, pt.ingredients
        FROM orders o
        JOIN order_details od ON o.order_id = od.order_id
        JOIN pizzas p ON od.pizza_id = p.pizza_id
        JOIN pizza_types pt ON p.pizza_type_id = pt.pizza_type_id
        """
        df = pd.read_sql(query, conn)
        conn.close()
        
    except Exception as e:
        st.sidebar.warning("⚠️ Không thể kết nối SQL Server. Đang tự động chuyển sang đọc từ file CSV tĩnh.")
        # Fallback: Đọc từ file CSV tĩnh nếu SQL Server chưa sẵn sàng
        order_details = pd.read_csv('order_details.csv')
        orders = pd.read_csv('orders.csv')
        pizza_types = pd.read_csv('pizza_types.csv', encoding='latin1')
        pizzas = pd.read_csv('pizzas.csv')
        
        df = pd.merge(order_details, pizzas, on='pizza_id', how='left')
        df = pd.merge(df, pizza_types, on='pizza_type_id', how='left')
        df = pd.merge(df, orders, on='order_id', how='left')

    # Tiền xử lý
    df['revenue'] = df['quantity'] * df['price']
    df['date'] = pd.to_datetime(df['date'])
    df['hour'] = pd.to_datetime(df['time'], format='%H:%M:%S').dt.hour
    df['day_of_week'] = df['date'].dt.day_name()

    # Feature Engineering
    df['is_weekend'] = df['day_of_week'].isin(['Saturday', 'Sunday'])
    
    def get_part_of_day(hour):
        if 5 <= hour < 11:
            return 'Sáng (Morning)'
        elif 11 <= hour < 14:
            return 'Trưa (Afternoon)'
        elif 14 <= hour < 17:
            return 'Chiều (Late Afternoon)'
        elif 17 <= hour < 21:
            return 'Tối (Evening)'
        else:
            return 'Khuya (Night)'
            
    df['part_of_day'] = df['hour'].apply(get_part_of_day)
    
    # Phân loại quy mô đơn hàng (Order Size)
    if 'order_id' in df.columns:
        order_totals = df.groupby('order_id')['revenue'].sum().reset_index()
        order_totals.rename(columns={'revenue': 'total_order_value'}, inplace=True)
        
        def get_order_size(val):
            if val < 20:
                return 'Nhỏ (Small)'
            elif val < 50:
                return 'Vừa (Medium)'
            else:
                return 'Lớn (Large)'
        order_totals['order_size'] = order_totals['total_order_value'].apply(get_order_size)
        
        df = pd.merge(df, order_totals, on='order_id', how='left')
        
    return df

df_merged = load_data()

# --- 2. GIAO DIỆN CHÍNH (DASHBOARD) ---
st.title("🍕 F&B Operations Dashboard")
st.markdown("Hệ thống Phân tích và Dự báo Tối ưu hóa Vận hành")

# KPI Cards
total_revenue = df_merged['revenue'].sum()
total_orders = df_merged['order_id'].nunique() if 'order_id' in df_merged.columns else len(df_merged)
avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
total_pizzas = df_merged['quantity'].sum() if 'quantity' in df_merged.columns else 0
pizzas_per_order = total_pizzas / total_orders if total_orders > 0 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Tổng Doanh Thu", f"${total_revenue:,.2f}")
col2.metric("Tổng Đơn Hàng", f"{total_orders:,}")
col3.metric("AOV (Giá Trị/Đơn)", f"${avg_order_value:,.2f}")
col4.metric("Số Pizza/Đơn", f"{pizzas_per_order:,.1f}")

st.markdown("---")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📊 Phân tích Vận hành (EDA)", "🧠 Phân tích Nâng cao", "📈 Dự báo Tương lai (Forecasting)", "📦 Quản lý Kho"])

with tab1:
    st.subheader("Phân tích Lưu lượng Khách hàng (Tối ưu Nhân sự)")
    c1, c2 = st.columns(2)
    with c1:
        # Giờ cao điểm (Theo Buổi)
        if 'part_of_day' in df_merged.columns:
            orders_by_part = df_merged.groupby('part_of_day').size().reset_index(name='count')
            # Sort order
            part_order = ['Sáng (Morning)', 'Trưa (Afternoon)', 'Chiều (Late Afternoon)', 'Tối (Evening)', 'Khuya (Night)']
            orders_by_part['part_of_day'] = pd.Categorical(orders_by_part['part_of_day'], categories=part_order, ordered=True)
            orders_by_part = orders_by_part.sort_values('part_of_day')
            
            fig, ax = plt.subplots(figsize=(8, 4))
            sns.barplot(data=orders_by_part, x='part_of_day', y='count', palette='viridis', ax=ax)
            ax.set_title("Số lượng món theo Buổi")
            plt.xticks(rotation=15)
            st.pyplot(fig)
        else:
            orders_by_hour = df_merged.groupby('hour').size().reset_index(name='count')
            fig, ax = plt.subplots(figsize=(8, 4))
            sns.barplot(data=orders_by_hour, x='hour', y='count', palette='viridis', ax=ax)
            ax.set_title("Số lượng món theo Giờ (Cao điểm)")
            st.pyplot(fig)
    
    with c2:
        # Doanh thu theo Size
        st.markdown("**Tỷ trọng Doanh thu theo Kích cỡ**")
        rev_by_size = df_merged.groupby('size')['revenue'].sum()
        st.bar_chart(rev_by_size)

with tab2:
    st.subheader("Phân tích Giỏ hàng (Cross-selling) & Điểm dị biệt")
    c2_1, c2_2 = st.columns(2)
    
    with c2_1:
        st.markdown("**Top Các cặp Pizza mua cùng nhau**")
        if 'order_id' in df_merged.columns:
            # Nhóm các pizza_id trong cùng 1 đơn hàng
            basket = df_merged.groupby('order_id')['name'].apply(list)
            # Lấy các đơn có từ 2 sản phẩm trở lên
            basket = basket[basket.apply(len) >= 2]
            from itertools import combinations
            from collections import Counter
            pair_counter = Counter()
            for items in basket:
                pair_counter.update(combinations(sorted(items), 2))
            
            top_pairs = pair_counter.most_common(5)
            if top_pairs:
                pair_df = pd.DataFrame(top_pairs, columns=['Cặp Pizza', 'Số lần mua chung'])
                pair_df['Cặp Pizza'] = pair_df['Cặp Pizza'].apply(lambda x: f"{x[0]} & {x[1]}")
                st.dataframe(pair_df, hide_index=True)
            else:
                st.info("Không có đủ dữ liệu đơn hàng mua nhiều sản phẩm.")
                
    with c2_2:
        st.markdown("**Phát hiện doanh thu bất thường (Outliers)**")
        daily_rev = df_merged.groupby('date')['revenue'].sum().reset_index()
        # Tính IQR
        Q1 = daily_rev['revenue'].quantile(0.25)
        Q3 = daily_rev['revenue'].quantile(0.75)
        IQR = Q3 - Q1
        upper_bound = Q3 + 1.5 * IQR
        outliers = daily_rev[daily_rev['revenue'] > upper_bound]
        
        fig_outlier, ax_outlier = plt.subplots(figsize=(6, 4))
        sns.boxplot(y=daily_rev['revenue'], ax=ax_outlier, color='lightblue')
        ax_outlier.set_title("Phân bố Doanh thu ngày")
        ax_outlier.set_ylabel("Doanh thu ($)")
        st.pyplot(fig_outlier)
        
        if not outliers.empty:
            st.warning(f"Phát hiện {len(outliers)} ngày có doanh thu đột biến (Vượt ${upper_bound:,.0f}).")
        else:
            st.success("Doanh thu các ngày ổn định, không có đột biến.")

with tab3:
    st.subheader("Dự báo Doanh thu 30 ngày tới (Machine Learning)")
    st.markdown("Sử dụng thuật toán **Exponential Smoothing (Holt-Winters)** để phân tích chuỗi thời gian doanh thu lịch sử và dự đoán tương lai.")
    
    # Gom nhóm doanh thu theo ngày
    daily_revenue = df_merged.groupby('date')['revenue'].sum().reset_index()
    daily_revenue.set_index('date', inplace=True)
    daily_revenue = daily_revenue.asfreq('D').fillna(0) # Đảm bảo dữ liệu liên tục theo ngày
    
    # Huấn luyện mô hình
    try:
        model = ExponentialSmoothing(daily_revenue['revenue'], trend='add', seasonal='add', seasonal_periods=7).fit()
        forecast = model.forecast(30) # Dự báo 30 ngày
        
        # Vẽ biểu đồ
        fig3, ax3 = plt.subplots(figsize=(12, 5))
        ax3.plot(daily_revenue.index, daily_revenue['revenue'], label='Doanh thu Thực tế (Quá khứ)', color='blue')
        
        # Vẽ đường dự báo nối tiếp
        forecast_index = pd.date_range(start=daily_revenue.index[-1] + pd.Timedelta(days=1), periods=30)
        ax3.plot(forecast_index, forecast, label='Doanh thu Dự báo (30 ngày tới)', color='red', linestyle='--')
        
        ax3.set_title("Biểu đồ Dự báo Doanh thu Tương lai", fontsize=14)
        ax3.set_ylabel("Doanh thu ($)")
        ax3.legend()
        st.pyplot(fig3)
        
        # Hiện bảng data dự báo
        st.markdown("**Dữ liệu dự kiến:**")
        forecast_df = pd.DataFrame({'Ngày dự báo': forecast_index.date, 'Doanh thu dự kiến ($)': forecast.values})
        st.dataframe(forecast_df.head(7)) # Hiển thị 7 ngày đầu
        
    except Exception as e:
        st.error(f"Có lỗi khi chạy mô hình dự báo: {e}")

with tab4:
    st.subheader("Tối ưu hóa Tồn kho Nguyên liệu")
    # Phân tách nguyên liệu
    from collections import Counter
    ingredient_counts = Counter()
    for index, row in df_merged.dropna(subset=['ingredients']).iterrows():
        ing_list = [i.strip() for i in row['ingredients'].split(',')]
        for ing in ing_list:
            ingredient_counts[ing] += row['quantity']
            
    top_ing = pd.DataFrame.from_dict(ingredient_counts, orient='index', columns=['consumed']).sort_values('consumed', ascending=False).head(10).reset_index()
    
    fig4, ax4 = plt.subplots(figsize=(10, 4))
    sns.barplot(data=top_ing, x='consumed', y='index', palette='cubehelix', ax=ax4)
    ax4.set_title("Top 10 Nguyên liệu tiêu thụ nhiều nhất")
    ax4.set_xlabel("Số lượng bán ra")
    ax4.set_ylabel("Nguyên liệu")
    st.pyplot(fig4)

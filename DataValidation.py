import io
import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

st.set_page_config(
    page_title="النظام الذكي الموحد للتحليل المالي والضريبي",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main, .stApp {
        direction: ltr !important;
        text-align: left !important;
    }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 6px 15px rgba(0, 0, 0, 0.06);
        border: 1px solid #e2e8f0;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("📊 النظام السحابي الموحد للتحليل المالي والضريبي (PostgreSQL)")
st.markdown(
    "تجميع، دمج الحسابات، الإدارة الذكية للضرائب، ومعاينة وتصدير تقرير الإقرار"
    " الضريبي الرسمي بدقة."
)

UPLOAD_DIR = "attachments"
if not os.path.exists(UPLOAD_DIR):
  os.makedirs(UPLOAD_DIR)

DATABASE_URL = st.secrets.get(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/tax_db",
)

@st.cache_resource
def get_db_engine():
  try:
    engine = create_engine(DATABASE_URL)
    return engine
  except Exception as e:
    st.error(f"خطأ في الاتصال بقاعدة البيانات: {e}")
    return None

engine = get_db_engine()

TAX_OPTIONS = [
    "خاضع للضريبة (15%)",
    "رسوم بنكية خاضعة للضريبة (15%)",
    "معفي / غير خاضع",
    "مشتريات خارجية (غير خاضعة)",
    "رسوم بنكية/غير خاضعة",
]

ATTACHMENT_ACTIONS = [
    "--- اختر إجراء ---",
    "📂 استعراض / معاينة المرفق",
    "📥 تحميل الملف",
    "📎 رفع أو استبدال ملف",
    "🗑️ حذف المرفق",
]

def smart_classify_tax(row):
    desc = str(row.get("التفاصيل", "")).upper()
    if "FEE" in desc or "VAT AMOUNT" in desc:
        return "رسوم بنكية خاضعة للضريبة (15%)"
    if "مريم نزار بن عبدالله موسى" in str(row.get("التفاصيل", "")) or "شخصي" in desc or "ادخار" in desc:
        return "معفي / غير خاضع"
    is_external = (
        "SWF-" in desc or 
        "TURKEY" in desc or "BAHRAIN" in desc or "UNITED ARAB EMIRATES" in desc or "UAE" in desc or "DUBAI" in desc or
        ("TO:" in desc and "SAR" not in desc[:desc.find("TO:")] and ("USD" in desc or "EUR" in desc or "AED" in desc))
    )
    if is_external:
        return "مشتريات خارجية (غير خاضعة)"
    return "خاضع للضريبة (15%)"

def calculate_vat_value(row):
    tax_status = str(row.get("التصنيف الضريبي", ""))
    if "غير خاضعة" in tax_status or "معفي" in tax_status or "غير خاضع" in tax_status:
        return 0.0
    if "خاضع" in tax_status:
        inflow = float(row.get("الوارد", 0) or 0)
        outflow = float(row.get("المنصرف", 0) or 0)
        total_amount = inflow if inflow > 0 else outflow
        vat = (total_amount / 1.15) * 0.15
        return round(vat, 2)
    return 0.0

def load_data_from_pg():
  if engine:
    try:
      query = "SELECT * FROM central_bank_transactions"
      df = pd.read_sql(query, engine)
      if "id" not in df.columns:
        df.insert(0, "id", range(1, len(df) + 1))
      if "المرفقات / الفاتورة" not in df.columns:
        df["المرفقات / الفاتورة"] = ""
      return df
    except Exception:
      return pd.DataFrame()
  return pd.DataFrame()

def save_data_to_pg(new_df):
  if engine:
    try:
      existing_df = load_data_from_pg()
      if "id" in new_df.columns:
        new_df = new_df.drop(columns=["id"])
      if not existing_df.empty and "id" in existing_df.columns:
        existing_df = existing_df.drop(columns=["id"])

      if not existing_df.empty:
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        subset_cols = [c for c in ["التاريخ", "الوارد", "المنصرف", "رقم المرجع"] if c in combined.columns]
        cleaned_df = combined.drop_duplicates(subset=subset_cols, keep="first")
      else:
        cleaned_df = new_df

      cleaned_df.to_sql("central_bank_transactions", engine, if_exists="replace", index=False)
      return True
    except Exception as e:
      st.error(f"خطأ أثناء الحفظ في قاعدة البيانات: {e}")
      return False
  return False

def save_edited_data_to_pg(edited_df):
  if engine:
    try:
      if "id" in edited_df.columns:
        df_to_save = edited_df.drop(columns=["id"])
      else:
        df_to_save = edited_df
      df_to_save.to_sql("central_bank_transactions", engine, if_exists="replace", index=False)
      return True
    except Exception as e:
      st.error(f"خطأ أثناء تحديث قاعدة البيانات: {e}")
      return False
  return False

@st.dialog("📁 إدارة مرفق الفاتورة للحركة")
def open_attachment_dialog(trans_id):
    current_df = load_data_from_pg()
    row_data = current_df[current_df["id"] == trans_id]
    if row_data.empty:
        st.error("لم يتم العثور على بيانات هذه الحركة.")
        return
    r = row_data.iloc[0]
    amt = r['المنصرف'] if r['المنصرف'] > 0 else r['الوارد']
    st.markdown(f"**رقم السطر (م):** {r['id']}")
    st.markdown(f"**رقم المرجع:** {r['رقم المرجع']}")
    st.markdown(f"**المبلغ:** {amt:,.2f} ر.س | **التاريخ:** {r['التاريخ']}")
    st.markdown(f"**التفاصيل:** {r['التفاصيل']}")
    st.markdown("---")
    current_att = str(r['المرفقات / الفاتورة'])
    if pd.notnull(current_att) and current_att.strip() != "" and os.path.exists(current_att):
        st.success(f"📁 مرفق حالي: {os.path.basename(current_att)}")
    else:
        st.info("⚪ لا يوجد مرفق مرتبط بهذه الحركة حتى الآن.")
    uploaded_file = st.file_uploader("اختر ملف الفاتورة الجديد (صورة أو PDF):", type=["png", "jpg", "jpeg", "pdf"], key=f"dialog_up_{trans_id}")
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("💾 حفظ وربط المرفق", type="primary", key=f"save_att_{trans_id}"):
            if uploaded_file:
                file_path = os.path.join(UPLOAD_DIR, f"trans_{trans_id}_{uploaded_file.name}")
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                current_df.loc[current_df["id"] == trans_id, "المرفقات / الفاتورة"] = file_path
                if save_edited_data_to_pg(current_df):
                    st.success("✨ تم حفظ وربط المرفق بنجاح!")
                    st.rerun()
    with col_btn2:
        if pd.notnull(current_att) and current_att.strip() != "" and os.path.exists(current_att):
            if st.button("🗑️ حذف المرفق الحالي", key=f"del_att_{trans_id}"):
                current_df.loc[current_df["id"] == trans_id, "المرفقات / الفاتورة"] = ""
                if save_edited_data_to_pg(current_df):
                    st.success("🗑️ تم حذف المرفق بنجاح!")
                    st.rerun()

# -------------------------------------------------------------
# 1. قسم رفع ومعاينة ملفات كشف الحساب
# -------------------------------------------------------------
st.subheader("📁 رفع ومعاينة وربط ملفات كشف الحساب")
uploaded_files = st.file_uploader(
    "اختر ملف أو عدة ملفات كشف حساب (أكسل أو PDF)",
    type=["xlsx", "xls", "pdf"],
    accept_multiple_files=True,
    key="main_file_uploader"
)

if uploaded_files:
  all_dfs = []
  for file in uploaded_files:
    file_extension = file.name.split(".")[-1].lower()
    try:
      if file_extension in ["xlsx", "xls"]:
        df_temp = pd.read_excel(file)
        df_temp.columns = df_temp.columns.str.strip()
        df_temp["المصدر"] = file.name
        all_dfs.append(df_temp)
    except Exception as e:
      st.warning(f"تعذر قراءة الملف {file.name}: {e}")

  if all_dfs:
    raw_df = pd.concat(all_dfs, ignore_index=True)
    available_cols = list(raw_df.columns)
    
    st.markdown("---")
    st.subheader("⚙️ مطابقة وتنسيق أعمدة الملف مع النظام المركزي")
    
    col_map1, col_map2, col_map3, col_map4, col_map5, col_map6 = st.columns(6)
    
    with col_map1:
        default_date = next((c for c in available_cols if "تاريخ" in c or "date" in c.lower()), available_cols[0])
        mapped_date = st.selectbox("التاريخ", available_cols, index=available_cols.index(default_date), key="map_date")
    with col_map2:
        default_in = next((c for c in available_cols if "إيداع" in c or "وارد" in c or "credit" in c.lower()), available_cols[0])
        mapped_in = st.selectbox("الوارد", available_cols, index=available_cols.index(default_in), key="map_in")
    with col_map3:
        default_out = next((c for c in available_cols if "خصم" in c or "منصرف" in c or "debit" in c.lower()), available_cols[0])
        mapped_out = st.selectbox("المنصرف", available_cols, index=available_cols.index(default_out), key="map_out")
    with col_map4:
        default_ref = next((c for c in available_cols if "مرجع" in c or "ref" in c.lower()), available_cols[0])
        mapped_ref = st.selectbox("رقم المرجع", available_cols, index=available_cols.index(default_ref), key="map_ref")
    with col_map5:
        default_type = next((c for c in available_cols if "نوع" in c or "type" in c.lower() or "حركة" in c), available_cols[0])
        mapped_type = st.selectbox("نوع العملية", available_cols, index=available_cols.index(default_type), key="map_type")
    with col_map6:
        default_desc = next((c for c in available_cols if "تفاصيل" in c or "بيان" in c or "desc" in c.lower()), available_cols[0])
        mapped_desc = st.selectbox("التفاصيل", available_cols, index=available_cols.index(default_desc), key="map_desc")

    processed_df = pd.DataFrame()
    processed_df["التاريخ"] = raw_df[mapped_date]
    
    # تنظيف وقراءة الأرقام بشكل صحيح مع معالجة الفواصل والأسطر الفارغة
    processed_df["الوارد"] = pd.to_numeric(raw_df[mapped_in].astype(str).str.replace(',', ''), errors="coerce").fillna(0.0)
    processed_df["المنصرف"] = pd.to_numeric(raw_df[mapped_out].astype(str).str.replace(',', ''), errors="coerce").fillna(0.0)
    
    processed_df["رقم المرجع"] = raw_df[mapped_ref].astype(str)
    processed_df["نوع العملية"] = raw_df[mapped_type].astype(str)
    processed_df["التفاصيل"] = raw_df[mapped_desc].astype(str)
    processed_df["المصدر"] = raw_df["المصدر"]
    processed_df["المرفقات / الفاتورة"] = ""
    
    processed_df["التصنيف الضريبي"] = processed_df.apply(smart_classify_tax, axis=1)
    processed_df["قيمة الضريبة"] = processed_df.apply(calculate_vat_value, axis=1)

    st.markdown("---")
    st.subheader("👁️ معاينة وتعديل بيانات ملف الأكسل قبل الحفظ النهائي:")

    edited_preview_df = st.data_editor(
        processed_df,
        column_config={
            "التصنيف الضريبي": st.column_config.SelectboxColumn(
                "التصنيف الضريبي",
                options=TAX_OPTIONS,
                required=True,
            ),
        },
        hide_index=True,
        width="stretch",
        key="preview_data_editor",
    )

    for idx, row in edited_preview_df.iterrows():
        match_idx = processed_df[(processed_df["التاريخ"] == row["التاريخ"]) & 
                                   (processed_df["الوارد"] == row["الوارد"]) & 
                                   (processed_df["المنصرف"] == row["المنصرف"]) & 
                                   (processed_df["رقم المرجع"] == row["رقم المرجع"])].index
        if not match_idx.empty:
            processed_df.loc[match_idx, "التصنيف الضريبي"] = row["التصنيف الضريبي"]
            processed_df.loc[match_idx, "قيمة الضريبة"] = calculate_vat_value(processed_df.loc[match_idx[0]])

    if st.button("🚀 اعتماد وحفظ البيانات في قاعدة البيانات المركزية", type="primary"):
        if save_data_to_pg(processed_df):
            st.success("✨ تم دمج وحفظ البيانات بنجاح!")
            st.rerun()

st.markdown("---")

# -------------------------------------------------------------
# 2. استعراض وفلترة البيانات المركزية
# -------------------------------------------------------------
current_db_df = load_data_from_pg()

if not current_db_df.empty:
  st.subheader("🔍 سجل الحركات الموحد في قاعدة البيانات (PostgreSQL)")
  
  temp_df_dates = current_db_df.copy()
  temp_df_dates["parsed_date"] = pd.to_datetime(temp_df_dates["التاريخ"], errors="coerce")
  min_date_val = temp_df_dates["parsed_date"].min()
  max_date_val = temp_df_dates["parsed_date"].max()
  has_valid_dates = not pd.isna(min_date_val) and not pd.isna(max_date_val)

  with st.expander("🔍 خيارات البحث والتصفية المتقدمة (بالتاريخ، النص، والمبلغ)", expanded=True):
      f_col1, f_col2, f_col3 = st.columns(3)
      tax_filter_options = ["الكل"] + TAX_OPTIONS
      with f_col1:
          selected_tax_filter = st.selectbox("تصفية بحسب التصنيف الضريبي", tax_filter_options, key="db_tax")
      with f_col2:
          start_date = st.date_input("من تاريخ", value=min_date_val.date() if has_valid_dates else None, key="db_start")
      with f_col3:
          end_date = st.date_input("إلى تاريخ", value=max_date_val.date() if has_valid_dates else None, key="db_end")

      s_col1, s_col2 = st.columns(2)
      with s_col1:
          search_keyword = st.text_input("بحث نصي (رقم المرجع، نوع العملية، أو التفاصيل)", "", key="db_search")
      with s_col2:
          search_amount = st.number_input("بحث بمبلغ محدد (وارد أو منصرف - اتركها 0 لعدم التصفية)", value=0.0, step=10.0, format="%.2f", key="db_amount")

  filtered_db_df = current_db_df.copy()
  filtered_db_df["إجراءات المرفق"] = "--- اختر إجراء ---"
  display_table_df = filtered_db_df.drop(columns=["المرفقات / الفاتورة", "حالة المرفق"], errors="ignore")

  if selected_tax_filter != "الكل":
      display_table_df = display_table_df[display_table_df["التصنيف الضريبي"] == selected_tax_filter]
  
  if search_keyword:
      display_table_df = display_table_df[
          display_table_df["التفاصيل"].str.contains(search_keyword, case=False, na=False) |
          display_table_df["رقم المرجع"].str.contains(search_keyword, case=False, na=False) |
          display_table_df["نوع العملية"].str.contains(search_keyword, case=False, na=False)
      ]

  if search_amount > 0:
      display_table_df = display_table_df[
          (display_table_df["الوارد"] == search_amount) | (display_table_df["المنصرف"] == search_amount)
      ]

  if has_valid_dates and start_date and end_date:
      display_table_df["parsed_date"] = pd.to_datetime(display_table_df["التاريخ"], errors="coerce")
      mask = (display_table_df["parsed_date"].dt.date >= start_date) & (display_table_df["parsed_date"].dt.date <= end_date)
      display_table_df = display_table_df[mask].drop(columns=["parsed_date"])

  edited_db_df = st.data_editor(
      display_table_df,
      column_config={
          "id": st.column_config.NumberColumn("م", disabled=True),
          "إجراءات المرفق": st.column_config.SelectboxColumn("⚙️ إدارة المرفق", options=ATTACHMENT_ACTIONS, required=True),
          "التصنيف الضريبي": st.column_config.SelectboxColumn("الحالة والتصنيف الضريبي", options=TAX_OPTIONS, required=True),
      },
      hide_index=True,
      width="stretch",
      key="pg_data_editor",
  )

  for idx, row in edited_db_df.iterrows():
      chosen_action = row["إجراءات المرفق"]
      s_id = row["id"]
      if chosen_action != "--- اختر إجراء ---":
          orig_row = current_db_df[current_db_df["id"] == s_id].iloc[0]
          curr_path = str(orig_row["المرفقات / الفاتورة"])
          if "رفع أو استبدال" in chosen_action:
              open_attachment_dialog(s_id)
          elif "استعراض" in chosen_action:
              if pd.notnull(curr_path) and curr_path.strip() != "" and os.path.exists(curr_path):
                  open_attachment_dialog(s_id)
          elif "حذف" in chosen_action:
              current_db_df.loc[current_db_df["id"] == s_id, "المرفقات / الفاتورة"] = ""
              if save_edited_data_to_pg(current_db_df):
                  st.success(f"🗑️ تم حذف مرفق السطر ({s_id}) بنجاح!")
                  st.rerun()

  for idx, row in edited_db_df.iterrows():
      orig_idx = current_db_df[current_db_df["id"] == row["id"]].index
      if not orig_idx.empty:
          current_db_df.loc[orig_idx, "التصنيف الضريبي"] = row["التصنيف الضريبي"]
          current_db_df.loc[orig_idx, "قيمة الضريبة"] = calculate_vat_value(current_db_df.loc[orig_idx[0]])

  if st.button("💾 حفظ تعديلات التصنيفات في قاعدة البيانات", type="primary", key="save_edits_btn"):
      if save_edited_data_to_pg(current_db_df):
          st.success("✨ تم تحديث وحفظ التغييرات بنجاح!")
          st.rerun()

  st.markdown("---")
  st.subheader("📊 لوحة المؤشرات الضريبية والمالية الإجمالية")

  calc_df = display_table_df
  inflow_df = calc_df[calc_df["الوارد"] > 0]
  total_inflow = inflow_df["الوارد"].sum()
  taxable_inflow_net = inflow_df[inflow_df["التصنيف الضريبي"].str.contains("خاضع") & ~inflow_df["التصنيف الضريبي"].str.contains("غير خاضعة")]["الوارد"].sum() / 1.15
  sales_vat = inflow_df[inflow_df["التصنيف الضريبي"].str.contains("خاضع") & ~inflow_df["التصنيف الضريبي"].str.contains("غير خاضعة")]["قيمة الضريبة"].sum()

  outflow_df = calc_df[calc_df["المنصرف"] > 0]
  total_outflow = outflow_df["المنصرف"].sum()
  
  taxable_outflow_df = outflow_df[outflow_df["التصنيف الضريبي"].str.contains("خاضع") & ~outflow_df["التصنيف الضريبي"].str.contains("غير خاضعة")]
  taxable_outflow_net = taxable_outflow_df["المنصرف"].sum() / 1.15
  purchases_vat = taxable_outflow_df["قيمة الضريبة"].sum()

  exempt_outflow_net = outflow_df[outflow_df["التصنيف الضريبي"].str.contains("معفي") | outflow_df["التصنيف الضريبي"].str.contains("غير خاضع")]["المنصرف"].sum()
  external_outflow_net = outflow_df[outflow_df["التصنيف الضريبي"].str.contains("خارجية")]["المنصرف"].sum()

  col1, col2, col3 = st.columns(3)
  col1.metric("إجمالي الوارد العام", f"{total_inflow:,.2f} ر.س")
  col2.metric("الإيرادات الخاضعة (الصافي)", f"{taxable_inflow_net:,.2f} ر.س")
  col3.metric("إجمالي ضريبة المبيعات (15%)", f"{sales_vat:,.2f} ر.س")

  col4, col5, col6 = st.columns(3)
  col4.metric("إجمالي المنصرف العام", f"{total_outflow:,.2f} ر.س")
  col5.metric("المصروفات الخاضعة (الصافي)", f"{taxable_outflow_net:,.2f} ر.س")
  col6.metric("إجمالي ضريبة المشتريات (15%)", f"{purchases_vat:,.2f} ر.س")

  # -------------------------------------------------------------
  # 3. صفحة معاينة وتصدير تقرير الإقرار الضريبي الرسمي
  # -------------------------------------------------------------
  st.markdown("---")
  st.markdown("## 📄 معاينة صفحة الإقرار الضريبي الرسمي (ZATCA)")

  start_date_str = str(start_date) if has_valid_dates and start_date else "غير محدد"
  end_date_str = str(end_date) if has_valid_dates and end_date else "غير محدد"

  net_sales = taxable_inflow_net
  vat_sales = sales_vat
  net_purchases = taxable_outflow_net
  vat_purchases = purchases_vat
  net_vat_due = vat_sales - vat_purchases

  st.markdown(
      f"""
      <div style="background-color: #f8f9fa; padding: 25px; border-radius: 12px; border: 1px solid #e2e8f0; direction: rtl; text-align: right;">
          <h3 style="color: #1b365d; margin-bottom: 5px;">الإقرار الضريبي لضريبة القيمة المضافة</h3>
          <p style="color: #555555; font-size: 15px;">الفترة الضريبية من: <b>{start_date_str}</b> إلى: <b>{end_date_str}</b></p>
      </div>
      """,
      unsafe_allow_html=True
  )

  st.markdown("<br>", unsafe_allow_html=True)

  zatca_page_data = {
      "البند الرئيسي في الإقرار": [
          "1 - المبيعات المحلية الخاضعة لضريبة القيمة المضافة (15%)",
          "2 - مبيعات العملاء المسجلين في دول مجلس التعاون الخليجي",
          "3 - المبيعات المحلية الخاضعة لنسبة الصفر بالمائة",
          "4 - التصدير بنسبة صفر بالمائة",
          "5 - المبيعات المعفاة",
          "6 - إجمالي المبيعات (المخرجات)",
          "7 - المشتريات المحلية الخاضعة لضريبة القيمة المضافة الأساسية",
          "8 - الواردات الخاضعة لضريبة القيمة المضافة المدفوعة في الجمارك",
          "9 - الواردات الخاضعة لضريبة القيمة المضافة من خلال آلية الاحتساب العكسي",
          "10 - المشتريات الخاضعة لنسبة صفر بالمائة",
          "11 - المشتريات المعفاة أو غير الخاضعة",
          "12 - إجمالي المشتريات (المدخلات)",
          "13 - إجمالي ضريبة القيمة المضافة المستحقة عن الفترة الحالية",
          "14 - التصحيحات من الفترة السابقة",
          "15 - ضريبة القيمة المضافة التي تم ترحيلها من الفترة/الفترات السابقة",
          "16 - صافي الضريبة المستحقة (أو المستردة)"
      ],
      "المبلغ (ريال)": [
          f"{net_sales:,.2f}", "0.00", "0.00", "0.00", "0.00", f"{net_sales:,.2f}",
          f"{net_purchases:,.2f}", "0.00", "0.00", "0.00", f"{exempt_outflow_net + external_outflow_net:,.2f}", f"{net_purchases + exempt_outflow_net + external_outflow_net:,.2f}",
          "-", "-", "-", f"{net_vat_due:,.2f}"
      ],
      "التعديلات (ريال)": [
          "0.00", "0.00", "0.00", "0.00", "0.00", "0.00",
          "0.00", "0.00", "0.00", "0.00", "0.00", "0.00",
          "-", "-", "-", "-"
      ],
      "قيمة ضريبة القيمة المضافة (ريال)": [
          f"{vat_sales:,.2f}", "0.00", "0.00", "0.00", "0.00", f"{vat_sales:,.2f}",
          f"{vat_purchases:,.2f}", "0.00", "0.00", "0.00", "0.00", f"{vat_purchases:,.2f}",
          f"{vat_sales:,.2f}", "0.00", "0.00", f"{net_vat_due:,.2f}"
      ]
  }

  zatca_page_df = pd.DataFrame(zatca_page_data)
  st.dataframe(zatca_page_df, hide_index=True, width="stretch")

  st.markdown("<br>", unsafe_allow_html=True)

  def generate_zatca_excel(start_str, end_str, n_sales, v_sales, n_purch, v_purch, n_due):
      output = io.BytesIO()
      with pd.ExcelWriter(output, engine="openpyxl") as writer:
          header_df = pd.DataFrame({
              "بيانات الإقرار الضريبي": ["الإقرار الضريبي لضريبة القيمة المضافة", f"الفترة من: {start_str} إلى: {end_str}"]
          })
          header_df.to_excel(writer, index=False, sheet_name="ZATCA_Return", startrow=0)
          zatca_page_df.to_excel(writer, index=False, sheet_name="ZATCA_Return", startrow=3)
      output.seek(0)
      return output.getvalue()

  excel_bytes = generate_zatca_excel(start_date_str, end_date_str, net_sales, vat_sales, net_purchases, purchases_vat, net_vat_due)

  col_dl1, col_dl2 = st.columns([2, 2])
  with col_dl1:
      st.download_button(
          label="📥 تحميل تقرير الإقرار الضريبي الرسمي (Excel معتمد)",
          data=excel_bytes,
          file_name=f"ZATCA_VAT_Return_{start_date_str}_to_{end_date_str}.xlsx",
          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          type="primary",
          use_container_width=True
      )
else:
  st.info("📭 قاعدة البيانات فارغة حالياً. قم برفع ملفات كشف الحساب (Excel) واعتمدها للبدء في تغذية النظام المركزي.")
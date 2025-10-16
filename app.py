import streamlit as st
import pandas as pd
from datetime import datetime
import os
import tempfile
import gspread
from google.oauth2.service_account import Credentials
import json
from pdfrw import PdfReader, PdfWriter, PdfDict
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader as PyPdfReader, PdfWriter as PyPdfWriter
import io


def setup_google_sheets():
    """Initialize Google Sheets connection for both local and cloud"""
    try:
        # ✅ When running in Streamlit Cloud or Render
        if "GOOGLE_CREDENTIALS" in st.secrets:
            creds_json = st.secrets["GOOGLE_CREDENTIALS"]
            credentials = Credentials.from_service_account_info(creds_json)
            st.success("✅ Using Google credentials from secrets.")
        else:
            # ✅ Local development (use local file)
            with open("credentials.json") as f:
                creds_json = json.load(f)
            credentials = Credentials.from_service_account_info(creds_json)
            st.info("📁 Using local credentials.json")

        client = gspread.authorize(credentials)
        return client

    except Exception as e:
        st.error(f"❌ Google Sheets setup failed: {e}")
        return None

# Use this in your app
gc = setup_google_sheets()

def generate_pdf_prescription(patient_data):
    """Generate PDF prescription and FLATTEN it to make text visible"""
    try:
        template_path = "templates/prescription_template.pdf"
        
        if not os.path.exists(template_path):
            st.error(f"❌ PDF template not found at: {template_path}")
            return None
        
        # Step 1: Fill the form fields using pdfrw
        template = PdfReader(template_path)
        
        # Exact field mapping based on your debug output
        field_mapping = {
            '(patient_name)': patient_data['patient_name'],
            '(age)': str(patient_data['age']),
            '(date)': patient_data['date'],
            '(treatment)': patient_data['treatment_type'],
            '(follow_up)': patient_data['follow_up_date'],
            '(instructions)': patient_data['instructions']
        }
        
        st.write("### Filling PDF Fields:")
        fields_filled = 0
        for field in template.Root.AcroForm.Fields:
            field_name = field.T
            if field_name in field_mapping:
                field.V = field_mapping[field_name]
                fields_filled += 1
                st.write(f"✅ Filled: '{field_name}' with '{field_mapping[field_name]}'")
        
        # Save filled (but not flattened) PDF temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='_filled.pdf') as filled_tmp:
            filled_path = filled_tmp.name
            PdfWriter().write(filled_path, template)
        
        # Step 2: FLATTEN the PDF to make text permanently visible
        flattened_path = flatten_pdf(filled_path)
        
        # Clean up temporary filled PDF
        try:
            os.unlink(filled_path)
        except:
            pass
        
        st.success(f"✅ PDF generated and flattened! Filled {fields_filled} fields")
        return flattened_path
        
    except Exception as e:
        st.error(f"❌ PDF generation failed: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None

def flatten_pdf(input_path):
    """Flatten PDF form fields to make text permanently visible"""
    try:
        # Method 1: Using PyPDF2 (simpler approach)
        reader = PyPdfReader(input_path)
        writer = PyPdfWriter()
        
        # Copy all pages
        for page in reader.pages:
            writer.add_page(page)
        
        # Flatten the form fields
        if reader.get_fields():
            writer.update_page_form_field_values(writer.pages[0], {})
        
        # Save flattened PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='_flattened.pdf') as flattened_tmp:
            flattened_path = flattened_tmp.name
            with open(flattened_path, 'wb') as output_file:
                writer.write(output_file)
        
        return flattened_path
        
    except Exception as e:
        st.warning(f"PyPDF2 flattening failed, using alternative method: {str(e)}")
        # If PyPDF2 fails, return the original filled PDF
        return input_path

# [Keep the main function exactly the same]
# Page configuration
st.set_page_config(
    page_title="Prescription System",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

SHEET_NAME = "cosmoslim patient record"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1vT3HU5fv8LM8noNmlUkZqYbZyhG8gBWOrYx2MOm51mQ/edit#gid=0"

def setup_google_sheets():
    """Initialize Google Sheets connection"""
    try:
        if os.path.exists('credentials.json'):
            client = gspread.service_account(filename='credentials.json')
            st.success("✅ Using credentials from credentials.json file")
        else:
            st.warning("Google Sheets credentials not found. Please upload your credentials.json file.")
            uploaded_file = st.file_uploader("Upload credentials.json", type="json", key="creds_upload")
            if uploaded_file is not None:
                with open('credentials.json', 'wb') as f:
                    f.write(uploaded_file.getvalue())
                st.success("✅ Credentials saved successfully!")
                st.rerun()
            else:
                return None
        
        try:
            sheet = client.open(SHEET_NAME).sheet1
            st.success(f"✅ Connected to Google Sheet: {SHEET_NAME}")
            
            existing_data = sheet.get_all_records()
            if not existing_data:
                headers = [
                    "Timestamp", "Patient Name", "Age", "Date", "Treatment Type", 
                    "Session Number", "Follow-up Date", "Instructions", "Prescription ID"
                ]
                sheet.append_row(headers)
                st.info("📊 Added headers to existing sheet")
                
        except gspread.SpreadsheetNotFound:
            st.error(f"❌ Google Sheet '{SHEET_NAME}' not found!")
            return None
        
        return sheet
    
    except Exception as e:
        st.error(f"❌ Google Sheets setup failed: {str(e)}")
        st.info("ℹ️ You can still generate PDFs, but data won't be saved to Google Sheets.")
        return None

def save_to_google_sheets(sheet, patient_data):
    """Save prescription data to Google Sheets"""
    try:
        prescription_id = f"RX{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        row_data = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            patient_data['patient_name'],
            patient_data['age'],
            patient_data['date'],
            patient_data['treatment_type'],
            patient_data.get('session', 'N/A'),
            patient_data['follow_up_date'],
            patient_data['instructions'],
            prescription_id
        ]
        
        sheet.append_row(row_data)
        st.success(f"✅ Data saved to Google Sheets! Prescription ID: {prescription_id}")
        return prescription_id
        
    except Exception as e:
        st.error(f"❌ Failed to save to Google Sheets: {str(e)}")
        return None

def debug_pdf_fields():
    """Debug function to see ALL PDF field information"""
    try:
        template_path = "templates/prescription_template.pdf"
        
        if not os.path.exists(template_path):
            st.error(f"❌ PDF template not found at: {template_path}")
            return []
        
        template = PdfReader(template_path)
        
        st.subheader("🔍 PDF Form Field Analysis")
        
        if not hasattr(template.Root, 'AcroForm') or not template.Root.AcroForm.Fields:
            st.error("❌ No AcroForm fields found in PDF!")
            st.info("This PDF might not be a fillable form")
            return []
        
        all_fields = []
        
        st.write("### Found Form Fields:")
        for i, field in enumerate(template.Root.AcroForm.Fields):
            field_info = {
                'name': field.T if hasattr(field, 'T') else 'No Name',
                'type': field.FT if hasattr(field, 'FT') else 'No Type',
                'value': field.V if hasattr(field, 'V') else 'No Value',
                'rect': field.Rect if hasattr(field, 'Rect') else 'No Rect'
            }
            all_fields.append(field_info)
            
            st.write(f"**Field {i+1}:**")
            st.write(f"  - Name: `{field_info['name']}`")
            st.write(f"  - Type: `{field_info['type']}`")
            st.write(f"  - Current Value: `{field_info['value']}`")
            st.write(f"  - Rectangle: `{field_info['rect']}`")
            st.write("---")
        
        st.success(f"✅ Found {len(all_fields)} form fields")
        return all_fields
        
    except Exception as e:
        st.error(f"❌ Cannot read PDF: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return []

def create_prescription_form():
    """Create the prescription input form"""
    
    st.title("🏥 Dr. Heena Fatema - Prescription System")
    st.markdown("---")
    
    if 'sheet' in st.session_state and st.session_state.sheet:
        st.success("📊 Google Sheets: Connected")
        st.markdown(f"[View Google Sheet]({SHEET_URL})")
    else:
        st.warning("📊 Google Sheets: Not connected - PDFs will still generate")
    
    st.header("Create New Prescription")
    
    # Debug button
    if st.button("🔍 Debug PDF Fields"):
        debug_pdf_fields()
    
    col1, col2 = st.columns(2)
    
    with col1:
        patient_name = st.text_input(
            "Patient Name *", 
            placeholder="Enter full name",
            key="patient_name"
        )
        
        age = st.number_input(
            "Age *", 
            min_value=1, 
            max_value=120, 
            value=30,
            key="age"
        )
        
        date = st.date_input(
            "Date *", 
            value=datetime.now().date(),
            key="date"
        )
        
    with col2:
        treatment_options = ["Select Treatment", "Diode Laser", "HydraFacial", "Chemical Peel", "PRP Therapy"]
        treatment = st.selectbox(
            "Treatment Type *", 
            options=treatment_options,
            key="treatment"
        )
        
        session = "N/A"
        if treatment == "Diode Laser":
            session = st.number_input(
                "Session Number *", 
                min_value=1, 
                max_value=20, 
                value=1,
                key="session"
            )
        else:
            st.number_input(
                "Session Number", 
                min_value=1, 
                max_value=20, 
                value=1, 
                disabled=True, 
                key="disabled_session"
            )
            session = "N/A"
            
        follow_up = st.date_input(
            "Follow-up Date *", 
            value=datetime.now().date(),
            key="follow_up"
        )
    
    instructions = st.text_area(
        "Instructions", 
        placeholder="Enter patient instructions...", 
        height=100,
        key="instructions"
    )
    
    submitted = st.button("🚀 Generate Prescription", use_container_width=True, type="primary")
    
    if submitted:
        if not patient_name.strip():
            st.error("❌ Please enter patient name!")
            return None
            
        if treatment == "Select Treatment":
            st.error("❌ Please select a treatment type!")
            return None
        
        if treatment == "Diode Laser" and session == "N/A":
            st.error("❌ Please enter session number for Diode Laser treatment!")
            return None
        
        form_data = {
            'patient_name': patient_name.strip(),
            'age': age,
            'date': date.strftime("%d/%m/%Y"),
            'treatment_type': treatment,
            'follow_up_date': follow_up.strftime("%d/%m/%Y"),
            'instructions': instructions.strip(),
            'session': session
        }
        
        return form_data
    
    return None

def generate_pdf_prescription(patient_data):
    """Generate PDF prescription by filling form fields"""
    try:
        template_path = "templates/prescription_template.pdf"
        
        if not os.path.exists(template_path):
            st.error(f"❌ PDF template not found at: {template_path}")
            return None
        
        # First, let's see what fields are available
        template = PdfReader(template_path)
        
        if not hasattr(template.Root, 'AcroForm') or not template.Root.AcroForm.Fields:
            st.error("❌ No form fields found in PDF template!")
            st.info("Please ensure your PDF has fillable form fields")
            return None
        
        # Show what fields we're working with
        st.write("### Filling PDF Fields:")
        
        # Try different field name combinations
        field_attempts = [
            # Try exact field names from your PDF
            {'patient_name': patient_data['patient_name']},
            {'age': str(patient_data['age'])},
            {'date': patient_data['date']},
            {'treatment': patient_data['treatment_type']},
            {'follow_up': patient_data['follow_up_date']},
            {'instructions': patient_data['instructions']},
            {'session': str(patient_data['session']) if patient_data.get('session') != "N/A" else ""},
            
            # Try with common variations
            {'Patient Name': patient_data['patient_name']},
            {'Age': str(patient_data['age'])},
            {'Date': patient_data['date']},
            {'Treatment': patient_data['treatment_type']},
            {'Follow up': patient_data['follow_up_date']},
            {'Instructions': patient_data['instructions']},
            {'Session': str(patient_data['session']) if patient_data.get('session') != "N/A" else ""},
        ]
        
        fields_filled = 0
        for field in template.Root.AcroForm.Fields:
            field_name = field.T if hasattr(field, 'T') else 'Unknown'
            
            # Try to find matching data
            value_found = None
            for attempt in field_attempts:
                for key, value in attempt.items():
                    if key.lower() in field_name.lower() or field_name.lower() in key.lower():
                        value_found = value
                        break
                if value_found:
                    break
            
            if value_found is not None:
                field.V = value_found
                fields_filled += 1
                st.write(f"✅ Filled: '{field_name}' with '{value_found}'")
            else:
                st.write(f"❓ No match for field: '{field_name}'")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            output_path = tmp_file.name
        
        # Save the filled PDF
        PdfWriter().write(output_path, template)
        
        st.success(f"✅ PDF generated! Attempted to fill {fields_filled} fields")
        
        # IMPORTANT: Provide instructions to view filled PDF
        st.warning("""
        **Important Note for Viewing Filled PDF:**
        - Some PDF viewers (like Chrome) don't display filled form fields properly
        - **Download the PDF and open it in Adobe Acrobat Reader** to see the filled content
        - The data IS in the PDF, but some viewers don't render it correctly
        """)
        
        return output_path
        
    except Exception as e:
        st.error(f"❌ PDF generation failed: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None

def main():
    """Main application logic"""
    
    if 'sheet' not in st.session_state:
        st.session_state.sheet = setup_google_sheets()
    
    form_data = create_prescription_form()
    
    if form_data:
        st.subheader("📋 Prescription Data")
        st.write(f"**Patient Name:** {form_data['patient_name']}")
        st.write(f"**Age:** {form_data['age']}")
        st.write(f"**Date:** {form_data['date']}")
        st.write(f"**Treatment:** {form_data['treatment_type']}")
        st.write(f"**Session:** {form_data['session']}")
        st.write(f"**Follow-up Date:** {form_data['follow_up_date']}")
        st.write(f"**Instructions:** {form_data['instructions']}")
        
        prescription_id = None
        if st.session_state.sheet:
            with st.spinner("💾 Saving to Google Sheets..."):
                prescription_id = save_to_google_sheets(st.session_state.sheet, form_data)
        
        with st.spinner("📄 Generating prescription PDF..."):
            pdf_path = generate_pdf_prescription(form_data)
            
        if pdf_path:
            success_msg = f"🎉 Prescription for **{form_data['patient_name']}** generated successfully!"
            if prescription_id:
                success_msg += f" Prescription ID: **{prescription_id}**"
            st.success(success_msg)
            
            with open(pdf_path, "rb") as pdf_file:
                pdf_data = pdf_file.read()
            
            st.download_button(
                label="📄 Download Prescription PDF",
                data=pdf_data,
                file_name=f"prescription_{form_data['patient_name'].replace(' ', '_')}_{form_data['date'].replace('/', '-')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            
            try:
                os.unlink(pdf_path)
            except:
                pass
            
            st.info("💡 Ready to create another prescription? Refresh the page to start over.")

if __name__ == "__main__":

    main()


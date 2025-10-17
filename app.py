import streamlit as st
import pandas as pd
from datetime import datetime
import os
import tempfile
import gspread
from google.oauth2.service_account import Credentials
import json
from pdfrw import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io

# MUST BE FIRST - Page configuration
st.set_page_config(
    page_title="Prescription System",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# GLOBAL CONSTANTS
SHEET_NAME = "cosmoslim patient record"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1vT3HU5fv8LM8noNmlUkZqYbZyhG8gBWOrYx2MOm51mQ/edit#gid=0"

# Google Sheets setup
def setup_google_sheets():
    try:
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        
        if 'google_sheets' in st.secrets:
            creds_dict = json.loads(st.secrets['google_sheets']['credentials_json'])
            credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        else:
            with open('credentials.json') as f:
                creds_dict = json.load(f)
            credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        
        client = gspread.authorize(credentials)
        sheet = client.open(SHEET_NAME).sheet1
        st.success(f"✅ Connected to Google Sheet: {SHEET_NAME}")
        return sheet
    except Exception as e:
        st.error(f"❌ Google Sheets setup failed: {str(e)}")
        return None

def detect_field_positions():
    """Detect EXACT positions of all form fields in the template"""
    try:
        template_path = "templates/prescription_template.pdf"
        template = PdfReader(template_path)
        
        field_positions = {}
        
        for field in template.Root.AcroForm.Fields:
            if hasattr(field, 'T') and hasattr(field, 'Rect'):
                field_name = field.T
                x1, y1, x2, y2 = field.Rect
                
                # Calculate center position for writing text
                center_x = (float(x1) + float(x2)) / 2
                center_y = (float(y1) + float(y2)) / 2
                
                field_positions[field_name] = {
                    'x': center_x,
                    'y': center_y,
                    'width': float(x2) - float(x1),
                    'height': float(y2) - float(y1)
                }
        
        return field_positions
        
    except Exception as e:
        st.error(f"❌ Cannot detect field positions: {str(e)}")
        return {}

def generate_pdf_prescription(patient_data):
    """Generate PDF by writing text at EXACT field positions"""
    try:
        template_path = "templates/prescription_template.pdf"
        
        if not os.path.exists(template_path):
            st.error(f"❌ Template not found: {template_path}")
            return None
        
        # Step 1: Detect field positions
        with st.spinner("🔍 Detecting field positions..."):
            field_positions = detect_field_positions()
        
        if not field_positions:
            st.error("❌ Could not detect field positions")
            return None
        
        # Step 2: Field name mapping
        field_mapping = {
            'Name': patient_data['patient_name'],
            'Age': str(patient_data['age']),
            'Date': patient_data['date'],
            'Treatment': patient_data['treatment_type'],
            'Follow up': patient_data['follow_up_date'],
            'Instructions': patient_data['instructions'],
            'Session': str(patient_data.get('session', 'N/A'))
        }
        
        # Step 3: Create overlay PDF with text at exact positions
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=letter)
        
        # Set font
        c.setFont("Helvetica", 10)
        
        st.write("### 📝 Writing text at exact positions:")
        
        # Write text at detected positions
        fields_written = 0
        for template_field, value in field_mapping.items():
            # Find matching field in template
            for field_name, position in field_positions.items():
                if (template_field.lower() in field_name.lower() or 
                    field_name.lower() in template_field.lower()):
                    
                    x = position['x']
                    y = position['y']
                    
                    # Write text at exact field position
                    c.drawString(x, y, value)
                    fields_written += 1
                    st.write(f"✅ '{template_field}': '{value}' at ({x:.1f}, {y:.1f})")
                    break
        
        c.save()
        
        # Step 4: Merge overlay with template
        with st.spinner("🔄 Merging PDFs..."):
            output_path = merge_pdfs(template_path, packet.getvalue())
        
        st.success(f"✅ PDF generated! Wrote {fields_written} fields at exact positions")
        return output_path
        
    except Exception as e:
        st.error(f"❌ PDF generation failed: {str(e)}")
        return None

def merge_pdfs(template_path, overlay_data):
    """Merge template with text overlay"""
    try:
        # Read template
        template = PdfReader(template_path)
        
        # Read overlay
        overlay = PdfReader(io.BytesIO(overlay_data))
        
        # Merge: template as background, overlay as foreground
        for page in template.pages:
            if overlay.pages:
                page.PageContents = overlay.pages[0].PageContents
        
        # Save merged PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            output_path = tmp_file.name
            PdfWriter().write(output_path, template)
        
        return output_path
        
    except Exception as e:
        st.error(f"❌ PDF merge failed: {str(e)}")
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
    """Debug function to see field positions"""
    st.subheader("🔍 PDF Form Field Analysis")
    field_positions = detect_field_positions()
    
    if field_positions:
        for field_name, position in field_positions.items():
            st.write(f"**Field '{field_name}':**")
            st.write(f"  - Position: ({position['x']:.1f}, {position['y']:.1f})")
            st.write(f"  - Size: {position['width']:.1f} x {position['height']:.1f}")
            st.write("---")
        st.success(f"✅ Found {len(field_positions)} form fields")
    else:
        st.error("❌ No fields found or cannot read PDF")
    
    return field_positions

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
            
            # Clean up
            try:
                os.unlink(pdf_path)
            except:
                pass
            
            st.info("💡 Ready to create another prescription? Refresh the page to start over.")

if __name__ == "__main__":
    main()

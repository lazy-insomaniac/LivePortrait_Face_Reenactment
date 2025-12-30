import streamlit as st
import os
import cv2
import time
import subprocess
from PIL import Image
import numpy as np
from streamlit_cropper import st_cropper

# Import Backend
from src.config.argument_config import ArgumentConfig
from src.config.inference_config import InferenceConfig
from src.config.crop_config import CropConfig
from src.live_portrait_pipeline import LivePortraitPipeline
from src.evaluation_pipeline import EvaluationPipeline

# --- Helper Functions ---

def save_uploaded_file(uploaded_file, save_dir="temp_uploads"):
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    file_path = os.path.join(save_dir, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

def get_video_duration(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened(): return 0
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frame_count / fps if fps > 0 else 0
    cap.release()
    return duration

def trim_video_file(video_path, start_time, end_time):
    if start_time == 0 and end_time == 0: return video_path
    base, ext = os.path.splitext(video_path)
    output_path = f"{base}_trimmed_{start_time}_{end_time}{ext}"
    duration = end_time - start_time
    cmd = [
        "ffmpeg", "-y", "-ss", str(start_time), "-i", video_path,
        "-t", str(duration), "-c:v", "libx264", "-c:a", "aac", output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path

def crop_video_ffmpeg(video_path, crop_box):
    base, ext = os.path.splitext(video_path)
    output_path = f"{base}_cropped{ext}"
    x, y, w, h = crop_box['left'], crop_box['top'], crop_box['width'], crop_box['height']
    filter_str = f"crop={w}:{h}:{x}:{y}"
    cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", filter_str, "-c:a", "copy", output_path]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path

def extract_first_frame(video_path):
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()
    if ret:
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    return None

# --- Custom Recorder Component ---
def render_custom_recorder(output_path):
    """
    Renders a UI for webcam recording with Start/Stop/Discard logic.
    """
    if 'rec_active' not in st.session_state: st.session_state.rec_active = False
    if 'rec_complete' not in st.session_state: st.session_state.rec_complete = False

    preview_placeholder = st.empty()
    col_ctrl, col_status = st.columns([1, 2])

    # 1. State: Recording Finished
    if st.session_state.rec_complete and os.path.exists(output_path):
        st.success("Video Captured!")
        st.video(output_path)
        if st.button("🗑️ Discard & Retake", use_container_width=True):
            st.session_state.rec_complete = False
            try: os.remove(output_path)
            except: pass
            st.rerun()
        return output_path

    # 2. State: Recording Active
    if st.session_state.rec_active:
        with col_ctrl:
            if st.button("⏹️ Stop Recording", type="primary", use_container_width=True):
                st.session_state.rec_active = False
                st.session_state.rec_complete = True
                st.rerun()

        # Capture Loop
        cap = cv2.VideoCapture(0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), 30.0, (width, height))

        while st.session_state.rec_active:
            ret, frame = cap.read()
            if not ret: break
            out.write(frame)

            # Preview (Mirror)
            frame_rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
            preview_placeholder.image(frame_rgb, caption="🔴 Recording...", use_container_width=True)
            time.sleep(0.01) # Yield to UI

        cap.release()
        out.release()

    # 3. State: Ready to Record
    else:
        # Show Live Preview
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret:
                frame_rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
                preview_placeholder.image(frame_rgb, caption="Camera Preview", use_container_width=True)
        else:
            st.error("Camera not detected.")

        with col_ctrl:
            if st.button("🔴 Start Recording", type="primary", use_container_width=True):
                st.session_state.rec_active = True
                st.rerun()

    return None

# --- Model Loading ---

@st.cache_resource
def load_models():
    inference_cfg = InferenceConfig()
    crop_cfg = CropConfig()
    generator = LivePortraitPipeline(inference_cfg=inference_cfg, crop_cfg=crop_cfg)
    evaluator = EvaluationPipeline(inference_cfg=inference_cfg, crop_cfg=crop_cfg)
    return generator, evaluator

# --- Main Interface ---

def main():
    st.set_page_config(layout="wide", page_title="LivePortrait Studio")
    st.title("🗣️ LivePortrait: Speech Therapy Edition")

    # Paths
    os.makedirs("temp_uploads", exist_ok=True)
    os.makedirs("temp_patients", exist_ok=True)
    os.makedirs("animations", exist_ok=True)

    # Load Models
    with st.spinner("Loading AI Models..."):
        generator, evaluator = load_models()

    # --- Sidebar ---
    with st.sidebar:
        st.header("🛠️ Settings")
        flag_do_crop = st.checkbox("Refine Face Detection", value=True)
        flag_paste_back = st.checkbox("Paste Back", value=True)
        flag_normalize_lip = st.checkbox("Neutral Start", value=True)
        flag_stitching = st.checkbox("Seamless Stitching", value=True)
        flag_relative_motion = st.checkbox("Relative Motion", value=True)
        driving_option = st.selectbox("Driving Mode", ["expression-friendly", "pose-friendly"], index=0)

    # --- Inputs ---
    col1, col2 = st.columns(2)

    # === COLUMN 1: IMAGE ===
    with col1:
        st.subheader("1. Source Identity")
        source_file = st.file_uploader("Upload Image", type=['jpg', 'png'])

        # State Management
        if 'src_path' not in st.session_state: st.session_state.src_path = None
        if 'img_is_cropped' not in st.session_state: st.session_state.img_is_cropped = False

        if source_file:
            file_path = save_uploaded_file(source_file)
            # Reset if new file
            if st.session_state.src_path != file_path and not st.session_state.img_is_cropped:
                st.session_state.src_path = file_path
                st.session_state.img_is_cropped = False

            if not st.session_state.img_is_cropped:
                img = Image.open(st.session_state.src_path)
                st.info("Adjust the white box to crop the face.")
                cropped_img = st_cropper(
                    img, realtime_update=True, box_color='#FFFFFF',
                    aspect_ratio=(1,1), key="src_cropper"
                )
                if st.button("✂️ Apply Image Crop", use_container_width=True):
                    save_path = os.path.join("temp_uploads", f"cropped_{source_file.name}")
                    cropped_img.save(save_path)
                    st.session_state.src_path = save_path
                    st.session_state.img_is_cropped = True
                    st.rerun()
            else:
                st.image(st.session_state.src_path, caption="Processed Source", use_container_width=True)
                if st.button("🔄 Reset Image", use_container_width=True):
                    st.session_state.img_is_cropped = False
                    st.session_state.src_path = save_uploaded_file(source_file)
                    st.rerun()

    # === COLUMN 2: DRIVING VIDEO ===
    with col2:
        st.subheader("2. Driving Motion")
        driving_file = st.file_uploader("Upload Video", type=['mp4', 'mov', 'avi'])

        if 'drv_path' not in st.session_state: st.session_state.drv_path = None
        if 'vid_is_cropped' not in st.session_state: st.session_state.vid_is_cropped = False

        if driving_file:
            file_path = save_uploaded_file(driving_file)
            if st.session_state.drv_path is None or (file_path != st.session_state.drv_path and "cropped" not in st.session_state.drv_path):
                st.session_state.drv_path = file_path
                st.session_state.vid_is_cropped = False

            if not st.session_state.vid_is_cropped:
                frame = extract_first_frame(st.session_state.drv_path)
                if frame:
                    st.info("Crop the video using the first frame as reference.")
                    crop_box = st_cropper(
                        frame, realtime_update=True, box_color='#FFFFFF',
                        aspect_ratio=(1,1), return_type='box', key="vid_cropper"
                    )
                    if st.button("✂️ Apply Video Crop", use_container_width=True):
                        with st.spinner("Processing video..."):
                            new_path = crop_video_ffmpeg(st.session_state.drv_path, crop_box)
                            st.session_state.drv_path = new_path
                            st.session_state.vid_is_cropped = True
                            st.rerun()
            else:
                st.video(st.session_state.drv_path)
                if st.button("🔄 Reset Video", use_container_width=True):
                    st.session_state.vid_is_cropped = False
                    st.session_state.drv_path = save_uploaded_file(driving_file)
                    st.rerun()

    # --- Generation ---
    st.divider()
    if st.session_state.src_path and st.session_state.drv_path:
        if st.button("🚀 Generate Reenactment", type="primary", use_container_width=True):
            out_dir = "animations"
            args = ArgumentConfig(
                source=st.session_state.src_path,
                driving=st.session_state.drv_path,
                output_dir=out_dir,
                flag_do_crop=flag_do_crop, flag_pasteback=flag_paste_back,
                flag_normalize_lip=flag_normalize_lip, flag_stitching=flag_stitching,
                flag_relative_motion=flag_relative_motion, driving_option=driving_option
            )
            with st.spinner("Generating..."):
                generator.execute(args)
                files = [os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.endswith('.mp4')]
                if files:
                    st.session_state['generated_video'] = max(files, key=os.path.getctime)
                    st.rerun()

    # --- Evaluation ---
    if 'generated_video' in st.session_state:
        st.markdown("---")
        st.header("3. Results & Evaluation")

        c1, c2 = st.columns([1, 1])
        with c1:
            st.info("Reference Reenactment")
            st.video(st.session_state['generated_video'])

        with c2:
            st.success("Practice Evaluation")
            tab_up, tab_rec = st.tabs(["📤 Upload", "🔴 Record"])

            pat_path = None

            with tab_up:
                p_file = st.file_uploader("Upload Recording", type=['mp4', 'mov', 'webm'])
                if p_file: pat_path = save_uploaded_file(p_file, "temp_patients")

            with tab_rec:
                rec_path = os.path.join("temp_patients", "webcam_rec.mp4")
                recorded_file = render_custom_recorder(rec_path)
                if recorded_file: pat_path = recorded_file

            # Shared Logic for Patient Video (Crop -> Evaluate)
            if pat_path:
                # Track if this specific file is cropped
                if 'pat_path_track' not in st.session_state or st.session_state.pat_path_track != pat_path:
                    st.session_state.pat_path_track = pat_path
                    st.session_state.pat_is_cropped = False
                    st.session_state.pat_final_path = pat_path

                if not st.session_state.pat_is_cropped:
                    st.warning("Please crop your recording for accuracy.")
                    pf = extract_first_frame(st.session_state.pat_final_path)
                    if pf:
                        cp_box = st_cropper(pf, realtime_update=True, box_color='#FFFFFF', aspect_ratio=(1,1), return_type='box', key="pat_crop")
                        if st.button("✂️ Apply Practice Crop", use_container_width=True):
                            with st.spinner("Cropping..."):
                                new_p = crop_video_ffmpeg(st.session_state.pat_final_path, cp_box)
                                st.session_state.pat_final_path = new_p
                                st.session_state.pat_is_cropped = True
                                st.rerun()
                else:
                    st.video(st.session_state.pat_final_path)

                    if st.button("📊 Evaluate My Articulation", type="primary", use_container_width=True):
                        with st.spinner("Analyzing..."):
                            res = evaluator.evaluate(
                                reference_path=st.session_state['generated_video'],
                                patient_path=st.session_state.pat_final_path
                            )
                            if "error" in res:
                                st.error(res['error'])
                            else:
                                # Articulation
                                a_score = res['articulation_score']
                                st.metric("👄 Lip Articulation", f"{a_score}/100")
                                st.progress(a_score/100)

                                # Identity
                                i_score = res['identity_score']
                                st.caption(f"Identity Mismatch: {i_score}% (Should be low)")

                                # Feedback
                                st.write("### 🤖 Feedback")
                                for msg in res['feedback']: st.info(msg)

                    if st.button("Reset Recording", use_container_width=True):
                        st.session_state.pat_is_cropped = False
                        st.session_state.pat_final_path = st.session_state.pat_path_track
                        st.rerun()

if __name__ == "__main__":
    main()

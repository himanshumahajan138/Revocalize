import streamlit as st
import re
import shutil
import zipfile
from pathlib import Path
import pandas as pd
import torch
from code.audio_extractor import AudioExtractor
from code.audio_transcriber import AudioTranscriber
from code.options import whisper_languages, whisper_models
from code.audio_cloner.src.f5_tts.api import F5TTS
from code.thumbnail_generator import add_thumbnail_to_video

# --- Constants ---
CACHE_DIR = Path(".cache")
CACHE_OUTPUT_DIR = Path(f"{CACHE_DIR}/outputs")
CACHE_DIR.mkdir(exist_ok=True)
CACHE_OUTPUT_DIR.mkdir(exist_ok=True)

LANGUAGE_OPTIONS = whisper_languages
TRANSCRIPTION_MODEL_VARIANTS = whisper_models
CLEAN_SENTENCE = lambda s: re.sub(r"[^\w\s]", "", s).lower().split()


# --- Helper Functions ---
def save_uploaded_file(uploaded_file):
    file_path = CACHE_DIR / uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path


def reset_cache_dir():
    print("cleaning...")
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    CACHE_DIR.mkdir()
    torch.cuda.empty_cache()


def load_models(selected_language, selected_model_variant, selected_gpu):
    """Initialize all models with selected parameters."""

    reset_cache_dir()  # Ensure clean directory

    # Load all models with a spinner to show loading state
    with st.spinner(f"Loading models for {selected_language} on {selected_gpu}..."):

        transcriber = AudioTranscriber(
            language=selected_language,
            model_name=f"openai/whisper-{selected_model_variant}",
            device=selected_gpu.lower(),
        )

    return transcriber


def get_gpu_setting():
    """Determine GPU availability."""
    return "CUDA" if torch.cuda.is_available() else "CPU"


def reset_state_on_change(new_method, new_params):
    """
    Reset components when either input method or model parameters change.
    """
    # Reset on input method change
    if st.session_state.get("input_method") != new_method:
        st.session_state["input_method"] = new_method
        st.session_state["transcription"] = ""
        st.session_state["edited_data"] = pd.DataFrame()

    # Reset on model parameter change
    if st.session_state.get("model_params") != new_params:
        st.session_state["model_params"] = new_params
        st.session_state["transcription"] = ""
        st.session_state["edited_data"] = pd.DataFrame()


# --- Streamlit App ---
def main():
    # --- Sidebar ---
    st.sidebar.title("Model Settings")

    st.sidebar.subheader("Transcription Model", divider="orange")
    selected_language = st.sidebar.selectbox(
        "Select Language", list(LANGUAGE_OPTIONS.keys())
    )
    selected_model_variant = st.sidebar.selectbox(
        "Select Model Variant", TRANSCRIPTION_MODEL_VARIANTS
    )

    # GPU Setting with Validation
    system_gpu = get_gpu_setting()
    gpu_options = ["CUDA", "CPU"]
    selected_gpu = st.sidebar.radio(
        "GPU Setting", gpu_options, index=gpu_options.index(system_gpu)
    )

    if system_gpu == "CPU" and selected_gpu == "CUDA":
        st.sidebar.warning("CUDA is not available on this system. Defaulting to CPU.")
        selected_gpu = "CPU"

    # Initialize session state
    if "transcriber" not in st.session_state:
        st.session_state["transcriber"] = None
        st.session_state["model_params"] = {
            "language": None,
            "transcription_model_variant": None,
            "gpu": None,
        }
        st.session_state["input_method"] = ""  # Track current input method

    if "audio_file_path" not in st.session_state:
        st.session_state["audio_file_path"] = False

    if "video_file_path" not in st.session_state:
        st.session_state["video_file_path"] = False

    # Initialize session state flag for tracking submission
    if "processed_transcription_list" not in st.session_state:
        st.session_state["processed_transcription_list"] = False

    # Current model parameters
    current_params = {
        "language": selected_language,
        "model_variant": selected_model_variant,
        "gpu": selected_gpu,
    }

    # --- Main Page ---
    st.write("# 🎵 Revocalize 🎙️")

    st.subheader("Input Method", divider="orange")
    option = st.radio(
        "Choose an Input Method",
        ["Upload Video", "Upload Audio", "Live Capture"],
        horizontal=True,
    )

    # Reset state on change
    reset_state_on_change(option, current_params)

    # Load models if needed
    if (
        st.session_state["transcriber"] is None
        or st.session_state["model_params"] != current_params
    ):
        st.session_state["transcriber"] = load_models(
            selected_language,
            selected_model_variant,
            selected_gpu,
        )

    # Initialize session state for transcription and edited data
    if "transcription" not in st.session_state:
        st.session_state["transcription"] = ""
    if "text_boxes" not in st.session_state:
        st.session_state.text_boxes = []
    if "edited_data" not in st.session_state:
        st.session_state["edited_data"] = pd.DataFrame()
    # Store the generated files persistently
    if "generated_files" not in st.session_state:
        st.session_state["generated_files"] = []

    # File Upload Handling
    uploaded_file = None
    if option == "Upload Video":
        uploaded_file = st.file_uploader(
            "Upload a Video File", type=["mp4", "mkv", "avi"]
        )
    elif option == "Upload Audio":
        uploaded_file = st.file_uploader(
            "Upload an Audio File", type=["mp3", "wav", "aac"]
        )
    elif option == "Live Capture":
        st.info("Live capture is currently under development.")

    if uploaded_file and st.session_state["transcription"] == "":
        file_path = save_uploaded_file(uploaded_file)
        st.session_state["audio_file_path"] = file_path
        with st.spinner("Processing file..."):
            if option == "Upload Video":
                audio_file_path = AudioExtractor(
                    file_path, f"{file_path}.wav"
                ).extract_audio()
                st.session_state["audio_file_path"] = audio_file_path
                st.session_state["video_file_path"] = file_path

            # Use Transcriber to process uploaded file
            st.session_state["transcription"] = st.session_state[
                "transcriber"
            ].transcribe_file(st.session_state["audio_file_path"])
        st.success("Transcription completed successfully!")

    # Show transcription and editable data only after file is uploaded/processed
    if st.session_state["transcription"]:
        st.subheader("Transcription", divider="orange")
        st.code(body=st.session_state["transcription"], language=None, wrap_lines=True)
        words = CLEAN_SENTENCE(st.session_state["transcription"])
        st.subheader("Edit Transcription", divider="orange")
        if st.session_state.text_boxes == []:
            st.session_state.text_boxes = [st.session_state["transcription"]]
        # Display and manage text boxes with delete functionality
        for i, text in enumerate(st.session_state.text_boxes):
            cols = st.columns([8, 1], vertical_alignment="center")
            with cols[0]:
                st.session_state.text_boxes[i] = st.text_area(
                    label=f"Transcription No. : {i+1}",
                    label_visibility="visible",
                    value=text,
                    key=f"text_box_{i}"
                )
            with cols[1]:
                if i > 0:  # show this only if there are more than one trascription
                    st.button(
                        "❌",
                        key=f"delete_button_{i}",
                        on_click=lambda i=i: st.session_state.text_boxes.pop(i),
                        use_container_width=True,
                    )
        # Add a button to add new text boxes
        st.button(
            "Add Text Box",
            on_click=lambda: st.session_state.text_boxes.append(
                st.session_state["transcription"]
            ),
            use_container_width=True,
        )

        # --- Submit Button ---
        if st.button("Submit Changes", use_container_width=True):
            # Update edited data in session state
            # st.session_state["edited_data"].update(edited_df)
            with st.spinner("Submitting changes..."):
                # Process and save changes
                st.success("Changes submitted successfully!")

                processed_transcription_list = st.session_state.text_boxes
                # Show processed transcription beautifully
                st.subheader("Processed Transcriptions", divider="orange")

                def render_card(item, color="#1f1f1f"):
                    """Render a card for an item."""
                    st.markdown(
                        f"""
                        <div style="
                            background-color: {color}; 
                            padding: 15px; 
                            margin: 10px 0; 
                            border-radius: 10px; 
                            box-shadow: 2px 2px 8px rgba(0,0,0,0.1);
                        ">
                            <p style="font-size: 16px; color: #e0e0e0;">{item}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                # Render the top 3 items in columns
                top_items = processed_transcription_list[:3]
                if top_items:
                    cols = st.columns(len(top_items))
                    for col, item in zip(cols, top_items):
                        with col:
                            render_card(item, color="#252525")

                # Render remaining items in a scrollable container
                remaining_items = processed_transcription_list[3:]
                if remaining_items:
                    with st.expander(
                        "View All Processed Transcriptions", expanded=False
                    ):
                        st.markdown(
                            """
                            <div style="max-height: 300px; overflow-y: auto; padding: 10px;">
                            """,
                            unsafe_allow_html=True,
                        )
                        for item in remaining_items:
                            render_card(item)
                        st.markdown("</div>", unsafe_allow_html=True)
                st.session_state["processed_transcription_list"] = (
                    processed_transcription_list
                )

        # Display the list of generated videos or audio files
        if st.session_state["processed_transcription_list"]:
            # Generate new videos or audio files only when the button is clicked
            if st.button("Let's Create Videos", use_container_width=True):
                processed_transcription_list = st.session_state[
                    "processed_transcription_list"
                ]
                generated_files = []  # Temporary list for newly created files

                # Initialize progress bar outside of the loop
                progress_bar = st.progress(0)

                with st.spinner("Generating Videos..."):
                    for idx, processed_transcription in enumerate(
                        processed_transcription_list
                    ):
                        # Update the existing progress bar
                        changed_words = CLEAN_SENTENCE(processed_transcription)
                        different_words = [w for w in changed_words if w not in words]
                        different_words = (
                            ["default"] if different_words == [] else different_words
                        )
                        final_name = f"{CACHE_OUTPUT_DIR}/{'_'.join(different_words)}"

                        # Generate the audio or video file
                        wav, sr, spect = F5TTS().infer(
                            ref_file=st.session_state["audio_file_path"],
                            ref_text=st.session_state["transcription"],
                            gen_text=processed_transcription,
                            file_wave=f"{final_name}.wav",
                        )

                        # Update progress bar based on the iteration index
                        progress_bar.progress(
                            (idx + 1) / len(processed_transcription_list)
                        )

                        if option == "Upload Video":
                            final_file = AudioExtractor(
                                input_video=st.session_state["video_file_path"],
                                output_audio="final_cache.wav",
                            ).replace_audio(f"{final_name}.wav", f"{final_name}.mp4")
                            add_thumbnail_to_video(
                                final_name.split("/")[-1].replace("_", " "),
                                f"{final_name}.mp4",
                            )
                            generated_files.append(f"{final_name}.mp4")
                        elif option == "Upload Audio":
                            final_file = f"{final_name}.wav"
                            generated_files.append(final_file)

                # Update session state with newly generated files
                st.session_state["generated_files"].extend(generated_files)

            # Display previously generated files or newly generated ones
            if st.session_state["generated_files"]:
                st.subheader("Generated Outputs", divider="orange")
                cols = st.columns(3)  # Create three columns per row for better layout
                for i, file_path in enumerate(st.session_state["generated_files"]):
                    with cols[i % 3]:  # Distribute files across columns
                        if file_path.endswith(".mp4"):
                            st.video(file_path)

                            st.download_button(
                                label="Download Video",
                                data=open(file_path, "rb"),
                                file_name=file_path.split("/")[-1],
                                mime="video/mp4",
                                use_container_width=True,
                            )
                        elif file_path.endswith(".wav"):
                            st.audio(file_path)
                            st.download_button(
                                label="Download Audio",
                                data=open(file_path, "rb"),
                                file_name=file_path.split("/")[-1],
                                mime="audio/wav",
                                use_container_width=True,
                            )

            # Bulk download as ZIP
            if st.session_state["generated_files"]:
                zip_path = f"{CACHE_OUTPUT_DIR}/generated_files.zip"
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in st.session_state["generated_files"]:
                        zipf.write(file_path, Path(file_path).name)
                with open(zip_path, "rb") as zipf:
                    st.download_button(
                        label="Download All as ZIP",
                        data=zipf,
                        file_name="generated_files.zip",
                        mime="application/zip",
                        use_container_width=True,
                    )


if __name__ == "__main__":
    main()

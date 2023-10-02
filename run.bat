@echo off

python mascot.py ^
    --voicevox_path "C:\Users\xxx\AppData\Local\Programs\VOICEVOX\VOICEVOX.exe" ^
    --voice_changer_path "C:\MMVCServerSIO\start_http.bat" ^
    --image "chara/chara_image.png" ^
    --background_image "chara/background.png" ^
    --chatgpt_apikey "" ^
    --chatgpt_setting "chara/chara_setting.txt" ^
    --voicevox_speaker_name "ètì˙ïîÇ¬ÇﬁÇ¨" ^
    --rvc_pytorch_model_file "" ^
    --rvc_feature_file "" ^
    --rvc_index_file "" ^
    --voicevox_intonation_scale 1.0 ^
    --rvc_model_trans 0 ^
    --chatgpt_log "chatgpt.json" ^
    --chatgpt_log_replace ^
    --image_pipe_name "\\.\pipe\mascot_image_pipe" ^
    --run_command "client\MascotGirl_Client.exe -start_local"
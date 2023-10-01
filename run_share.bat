@echo off

python mascot.py ^
    --voicevox_path "C:\Users\xxx\AppData\Local\Programs\VOICEVOX\VOICEVOX.exe" ^
    --voice_changer_path "C:\MMVCServerSIO\start_http.bat" ^
    --image "chara/chara_image.png" ^
    --chatgpt_apikey "" ^
    --chatgpt_setting "chara/chara_setting.txt" ^
    --voicevox_speaker_name "ètì˙ïîÇ¬ÇﬁÇ¨" ^
    --rvc_pytorch_model_file "" ^
    --rvc_feature_file "" ^
    --rvc_index_file "" ^
    --voicevox_intonation_scale 1.0 ^
    --rvc_model_trans 0 ^
    --ngrok_auth_token "" ^
    --chatgpt_log "chatgpt.json" ^
    --chatgpt_log_replace ^
    --image_pipe_name "\\.\pipe\mascot_image_pipe" ^
    --framerate 30 ^
    --run_command_reload ^
    --run_command "ffmpeg\ffmpeg -y -loglevel error -f rawvideo -pix_fmt rgba -s 512x512 -framerate 30 -thread_queue_size 8192 -i \\.\pipe\mascot_image_pipe -f s16le -ar 48000 -ac 1 -thread_queue_size 8192 -i \\.\pipe\mascot_pipe -auto-alt-ref 0 -deadline realtime -quality realtime -cpu-used 4 -row-mt 1 -crf 30 -b:v 0 -pass 1 -c:v libvpx-vp9 -c:a libopus -f matroska tcp://0.0.0.0:55009/stream?listen"

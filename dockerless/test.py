import torch  
import whisper 
devices = torch.device("cuda:0" if torch.cuda.is_available() else "cpu") 
model = whisper.load_model("medium" , device =devices)

if torch.cuda.is_available():
    print("GPU!")
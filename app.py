import torch
from diffusers import StableDiffusionPipeline, DDIMScheduler, AutoencoderKL
from ip_adapter.ip_adapter_faceid import IPAdapterFaceID
from huggingface_hub import hf_hub_download
from insightface.app import FaceAnalysis
import gradio as gr
import cv2

base_model_path = "SG161222/Realistic_Vision_V4.0_noVAE"
vae_model_path = "stabilityai/sd-vae-ft-mse"
ip_ckpt = hf_hub_download(repo_id='h94/IP-Adapter-FaceID', filename="ip-adapter-faceid_sd15.bin", repo_type="model")

device = "cuda"

noise_scheduler = DDIMScheduler(
    num_train_timesteps=1000,
    beta_start=0.00085,
    beta_end=0.012,
    beta_schedule="scaled_linear",
    clip_sample=False,
    set_alpha_to_one=False,
    steps_offset=1,
)
vae = AutoencoderKL.from_pretrained(vae_model_path).to(dtype=torch.float16)
pipe = StableDiffusionPipeline.from_pretrained(
    base_model_path,
    torch_dtype=torch.float16,
    scheduler=noise_scheduler,
    vae=vae,
)

ip_model = IPAdapterFaceID(pipe, ip_ckpt, device)

def generate_image(images, prompt, negative_prompt, progress=gr.Progress(track_tqdm=True)):
    pipe.to(device)
    app = FaceAnalysis(name="buffalo_l", providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
    app.prepare(ctx_id=0, det_size=(640, 640))

    faceid_all_embeds = []
    for image in images:
        face = cv2.imread(image)
        faces = app.get(face)
        faceid_embed = torch.from_numpy(faces[0].normed_embedding).unsqueeze(0)
        faceid_all_embeds.append(faceid_embed)
    
    average_embedding = torch.mean(torch.stack(faceid_all_embeds, dim=0), dim=0)
    
    image = ip_model.generate(
        prompt=prompt, negative_prompt=negative_prompt, faceid_embeds=average_embedding, width=512, height=512, num_inference_steps=30
    )
    print(image)
    return image
css = '''
h1{margin-bottom: 0 !important}
'''
demo = gr.Interface(
        css=css,
        fn=generate_image,
        inputs=[
            gr.Files(
                label="Drag 1 or more photos of your face",
                file_types=["image"]
            ),
            gr.Textbox(label="Prompt",
                       info="Try something like 'a photo of a man/woman/person'",
                       placeholder="A photo of a [man/woman/person]..."),
            gr.Textbox(label="Negative Prompt", placeholder="low quality")
        ],
        outputs=[gr.Gallery(label="Generated Image")],
        title="IP-Adapter-FaceID demo",
        description="Demo for the IP-Adapter-FaceID,modified from https://huggingface.co/spaces/multimodalart/Ip-Adapter-FaceID",
        allow_flagging=False,
        )
demo.launch()
import time
import torch
import torchaudio
import torchvision
import librosa
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter1d
from config import set_params
from kws.model import treasure_net
from kws.utils.transforms import SpectogramNormalize
from kws.utils.utils import exp_moving_average


def test():
    # set parameters
    params = set_params()
    params['device'] = torch.device("cuda:0" if (torch.cuda.is_available()) else "cpu")
    if params['verbose']:
        print('Using device', params['device'])

    # initialize model
    model = treasure_net(params).to(params['device'])
    if params['load_model']:
        checkpoint = torch.load(params['model_checkpoint'])
        model.load_state_dict(checkpoint['model_state_dict'])

    # prepare test audio
    waveform, sample_rate = torchaudio.load(params['example_audio'])
    waveform = waveform[:1]
    print("sample_rate", sample_rate)
    print("wave size raw", waveform.size())

    # resample
    if sample_rate != params['sample_rate']:
        waveform = waveform.squeeze(0).numpy()
        waveform = librosa.core.resample(waveform, sample_rate, params['sample_rate'])
        waveform = torch.from_numpy(waveform).unsqueeze(0)

    print("wave size resample", waveform.size())

    waveform = waveform.to(params['device'])
    spectrogramer = torchvision.transforms.Compose([
        torchaudio.transforms.MelSpectrogram(
            sample_rate=params['sample_rate'],
            n_mels=params['num_mels'],
        ).to(params['device']),
        SpectogramNormalize(),
    ])

    # calculate keyword probs
    spec = spectrogramer(waveform).transpose(1, 2)
    print("spec", spec.size())
    num_predicts = spec.shape[1] - params['time_steps']
    print("time_steps", params['time_steps'])
    print("num_predict", num_predicts)
    keyword_probs = np.zeros((num_predicts, len(params['keywords'])))
    hidden = None

    for i in range(num_predicts):
        with torch.no_grad():
            logits, hidden = model(spec[:, i:i + params['time_steps']], hidden)
            probs = torch.nn.functional.softmax(logits.detach(), dim=-1).cpu().numpy()

        keyword_probs[i] = probs[:, 1:]

    # plot results
    plt.figure(figsize=(12, 5))
    plt.rcParams.update({'font.size': 14})

    seconds_steps = np.linspace(0, waveform.shape[1] / params['sample_rate'], num_predicts)
    for i, keyword in enumerate(params['keywords']):
        ema_probs = exp_moving_average(keyword_probs[:, i], alpha=params['ema_alpha'])
        plt.plot(seconds_steps, ema_probs, label=keyword)

    plt.grid()
    plt.legend(title='keyword')
    plt.xlabel('time (s)')
    plt.ylabel('probability')
    plt.savefig(params['example_fig'])


if __name__ == '__main__':
    test()

import os
import torch
import torchaudio

from django.core.management.base import BaseCommand

from transformers import ASTFeatureExtractor, AutoModelForAudioClassification

from ...models import Utterance


class Command(BaseCommand):
    help = 'This command classifies utterances using AST'

    def add_arguments(self, parser):
        parser.add_argument('collection_key', type=str)
        parser.add_argument('device', type=str)

    def fix(self, utternace, audio_type='unknown'):
        utternace.audio_type = audio_type
        utternace.save()

    def handle(self, *args, **options):
        collection_key = options['collection_key']
        device = options['device']

        # fix a bug with visiable CUDA GPUs
        os.environ['CUDA_VISIBLE_DEVICES'] = device.replace('cuda:', '')

        feature_extractor = ASTFeatureExtractor()
        model = AutoModelForAudioClassification.from_pretrained('MIT/ast-finetuned-audioset-10-10-0.4593').to(device)

        utterances = Utterance.objects.filter(collection_key=collection_key).all()

        for utterance in utterances:
            # skip a classified utterance
            if utterance.audio_type != '--':
                continue

            # load file
            waveform, sampling_rate = torchaudio.load(utterance.filename)
            waveform = waveform.squeeze().numpy()

            # get features
            inputs = feature_extractor(waveform, sampling_rate=sampling_rate, padding="max_length", return_tensors="pt").to(device)

            # detect class
            with torch.no_grad():
                outputs = model(inputs.input_values)

            # revert to human readable format
            predicted_class_idx = outputs.logits.argmax(-1).item()
            audio_type = model.config.id2label[predicted_class_idx]

            # save in DB
            self.fix(utterance, audio_type)

            self.stdout.write(f'{utterance.id}={audio_type}')
            self.stdout.write('---')

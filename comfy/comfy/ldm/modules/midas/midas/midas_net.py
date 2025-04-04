"""
midashnet: rede para estimativa de profundidade monocular treinada pela mistura de vários conjuntos de dados.

esse arquivo contém código adaptado de:
https://github.com/thomasjpfan/pytorch_refinenet/blob/master/pytorch_refinenet/refinenet/refinenet_4cascade.py
"""

import torch
import torch.nn as nn

from .base_model import BaseModel
from .blocks import FeatureFusionBlock, Interpolate, _make_encoder


class MidasNet(BaseModel):
    """
    rede para estimativa de profundidade monocular.
    """

    def __init__(self, path=None, features=256, non_negative=True):
        """inicializa.

        args:
            path (str, opcional): caminho para o modelo salvo. padrão é none.
            features (int, opcional): número de recursos. padrão é 256.
            backbone (str, opcional): rede de backbone para o encoder. padrão é resnext101_wsl
        """

        print("carregando pesos: ", path)

        super(MidasNet, self).__init__()

        use_pretrained = False if path is None else True

        self.pretrained, self.scratch = _make_encoder(backbone="resnext101_wsl", features=features, use_pretrained=use_pretrained)

        self.scratch.refinenet4 = FeatureFusionBlock(features)
        self.scratch.refinenet3 = FeatureFusionBlock(features)
        self.scratch.refinenet2 = FeatureFusionBlock(features)
        self.scratch.refinenet1 = FeatureFusionBlock(features)

        self.scratch.output_conv = nn.Sequential(
            nn.Conv2d(features, 128, kernel_size=3, stride=1, padding=1),
            Interpolate(scale_factor=2, mode="bilinear"),
            nn.Conv2d(128, 32, kernel_size=3, stride=1, padding=1),
            nn.ReLU(True),
            nn.Conv2d(32, 1, kernel_size=1, stride=1, padding=0),
            nn.ReLU(True) if non_negative else nn.Identity(),
        )

        if path:
            self.load(path)

    def forward(self, x):
        """passa pra frente.

        args:
            x (tensor): dados de entrada (imagem)

        retorna:
            tensor: profundidade
        """

        layer_1 = self.pretrained.layer1(x)
        layer_2 = self.pretrained.layer2(layer_1)
        layer_3 = self.pretrained.layer3(layer_2)
        layer_4 = self.pretrained.layer4(layer_3)

        layer_1_rn = self.scratch.layer1_rn(layer_1)
        layer_2_rn = self.scratch.layer2_rn(layer_2)
        layer_3_rn = self.scratch.layer3_rn(layer_3)
        layer_4_rn = self.scratch.layer4_rn(layer_4)

        path_4 = self.scratch.refinenet4(layer_4_rn)
        path_3 = self.scratch.refinenet3(path_4, layer_3_rn)
        path_2 = self.scratch.refinenet2(path_3, layer_2_rn)
        path_1 = self.scratch.refinenet1(path_2, layer_1_rn)

        out = self.scratch.output_conv(path_1)

        return torch.squeeze(out, dim=1)
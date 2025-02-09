# 基于神经网络捏脸


## Reinferences

```
1.  Unity-2019.2.1f1
2.  python-3.5
3.  tensorboardX
4.  dlib-19.18
5.  numpy-1.15.4
6.  torch-1.1.0
7.  opencv-contrib-python 3.4.0.12
8.  tqdm-4.23.4
9.  argparse-1.4.0
10. scipy-1.0.1
11. Pillow
```


## 论文

网易伏羲实验室、密歇根大学、北航和浙大的研究者提出了一种游戏角色自动创建方法，利用 Face-to-Parameter 的转换快速创建游戏角色，用户还可以自行基于模型结果再次进行修改，直到得到自己满意的人物。此项目按照[论文][i2]里的描述建立。


[Face-to-ParameterTranslationforGameCharacterAuto-Creation][i2]


![](/image/t2.jpeg)


## 引擎预览

打开Unity, 点击菜单栏Tools->Preview, 通过此工具可以手动去捏脸。当然， 此项目是通过神经网络生成参数params。

![](/image/t1.jpg)


## Database

打开Unity, 点击菜单栏Tools->GenerateDatabase

在export会生成两个文件夹trainset和testset， 分别用作训练集和测试集。 trainset随机生成的噪点大概是1/95。

这里由引擎随机生成2000张图片， 其中80%用作训练集， 20%用作验证集。同时在图片同目录会生成二进制文件db_description，记录捏脸相关的参数。

生成图片分辨率：512x512,  代替论文的是这里使用Unity引擎代替Justice引擎。

![](/image/t4.jpg)

## 脸部对齐 - Face alignment

对于输入图片，通过此工具dlib进行脸部截取。

```
pip3 install dlib
```

dlib 引用模型下载地址:

http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2 

http://dlib.net/files/dlib_face_recognition_resnet_model_v1.dat.bz2

##  LightCNN

[light_cnn][i5]出自2016 cvpr吴翔A Light CNN for Deep Face Representation with Noisy Labels，light_cnn优势在于一个很小的模型和一个非常不错的识别率。论文里使用LightCNN用于生成256 demonsion 信息，进而得到Loss函数L1, 即Discriminative Loss, 衡量引擎生成的图片和Imitator生成的图片差异。


训练好的模型下载连接：

google driver: [LightCNN-29 v2][i6]

baidu  yun:	   [LightCNN-29 v2][i7]


## 人脸分割


论文里使用人脸分割，提取局部面部特征， 从而计算Facial Content Loss， 下面列出了我网上找到相关的人脸分割的相关介绍和数据集。

1. 介绍

	
	[helen dataset 介绍]: http://www.ifp.illinois.edu/~vuongle2/helen

	[Exemplar-Based Face Parsing]: http://pages.cs.wisc.edu/~lizhang/projects/face-parsing/

	图像解析与编辑[中国科学院信息工程研究所网络空间技术实验室ppt]: https://pan.baidu.com/s/1FYznfGG914pPaU5bs0-4dw

2. 数据集

	helen_small4seg

	https://share.weiyun.com/5Q9ST03 密码：ndks4g



不同于论文里使用的resnet50，此项目引用的模型是resnet18。

预训练model:	https://pan.baidu.com/s/1AEc7CJGirsdxOouD3boRBQ  

下载后存放在face-parsing.PyTorch/res/cp 目录下


最后的效果如图：

![](/image/t3.jpg)


去掉skybox(背景), 然后隐藏掉身体和脖子部分， 处理效果后如下:

![](/image/t5.jpg)

利用openCV的candy算法， 提取脸部轮廓:

![](/image/t6.jpg)


## Operation


### 训练 train

进入git 下载目录， 按照下面命令就可以train， 训练的时候每隔100步会生成preview 图片，实时查看训练结果; 每隔500步就会保存下当前模型, 保存在model文件夹下

```sh
cd /path/to/workdir

cd neural/

mkdir dat/

# 这里需要将下载的lightcnn, dlib等模型拷贝过来
copy yours_download_model_path data/

python main.py \
	--phase=train_imitator \
	--batch_size=4 \
	--learning_rate=0.01 \
	--total_steps=30000	\
	--prev_freq=100	\
	--save_freq=500	\
	--path_to_dataset="../export/trainset_female/"

# 开启tensorboard 查看graph运行情况
tensorboard --logdir logs

```

### reinference

如果因为中间因为偶然因素（比如说断电）退出了训练， 又想从之前保存的model中恢复出来， 这时候可以先把model里的模型文件copy到reinference目录， 然后执行下面命令：

```sh
python main.py \
	--phase=inference_imitator	\
	--total_steps=30000	\
	--path_to_dataset="../export/trainset_female/"
```



[i1]: https://xueqiu.com/9217191040/133506937
[i2]: https://arxiv.org/abs/1909.01064
[i3]: http://www.sohu.com/a/339985351_823210
[i4]: https://blog.csdn.net/qiumokucao/article/details/81610628
[i5]: https://github.com/AlfredXiangWu/LightCNN
[i6]: https://drive.google.com/open?id=1Jn6aXtQ84WY-7J3Tpr2_j6sX0ch9yucS
[i7]: https://pan.baidu.com/s/1E_rGkbqzf0ppyl5ks9FSLQ
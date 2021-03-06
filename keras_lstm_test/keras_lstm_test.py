import numpy as np
import os
import sys
import random
from keras.preprocessing.text import Tokenizer
from keras.preprocessing.sequence import pad_sequences
from keras.utils.np_utils import to_categorical
from keras.models import Sequential, load_model, Model
from keras.layers import Embedding, LSTM, Dense, Activation, Input, Bidirectional
from keras.callbacks import TensorBoard, ModelCheckpoint

data_dir = "data"
text_data_dir = data_dir + '/20_newsgroup/'
max_sequence_length = 1000
max_nb_words = 20000    #max_features,即设置常用词阈值，从而限定embedding matrix的大小
embedding_dim = 100
validation_split = 0.2  #验证集比例
batch_size = 32

#将预训练的词向量文件中的词向量转换为容易查询的字典
embedding_index = {}
with open(os.path.join(data_dir, 'glove.6B.100d.txt'), encoding='utf-8') as f:
    for line in f:
        values = line.split()
        word = values[0]    #word
         #相应word的词向量vector，asarray与array都是将结构数据转化为array，区别在于asarray不会占用新内存
        vector = np.asarray(values[1:], dtype='float32')
        embedding_index[word] = vector
# print(embedding_index['hi'])
print("已匹配 %s 词向量" % len(embedding_index))

print("对文本数据进行处理")
texts = []  #text样本列表
labels_index = {}   #text原类名和label ID的字典
labels = [] #标签label的列表
for name in sorted(os.listdir(text_data_dir)):
    #遍历处理每种类别的text文件夹
    path = os.path.join(text_data_dir, name)
    if os.path.isdir(path):
        #为每种类别赋值label ID
        label_id = len(labels_index)    #一个小trick，根据当前列表长度为当前类别赋予类别名
        labels_index[name] = label_id
        for file_name in sorted(os.listdir(path)):
            #遍历处理每种类别下的所有text文件
            if file_name.isdigit():
                with open(os.path.join(path, file_name), encoding='latin-1') as file_path:
                    # print(sys.version_info)
                    # 将每个text文件及其对应的label添加到相应数组中
                    texts.append(file_path.read())
                    labels.append(label_id)
# print(labels_index['alt.atheism'])
# print(labels_index['comp.sys.ibm.pc.hardware'])
print('找到 %s 个texts' % len(texts))

#利用keras的Tokenizer对所有texts进行处理，主要将texts中的word映射到相应的index
tokenizer = Tokenizer()
tokenizer.fit_on_texts(texts)   #以texts作为训练的文本列表
# print("text:", type(texts), texts[5], type(texts[5]))
sequence = tokenizer.texts_to_sequences(texts)  #将文本列表转换为序列列表，每个序列对应一段文本
# print("sequence", type(sequence), sequence[5])  #证明在序列化后文本中的word已经替换成了对应的索引，所以后面可以直接根据embedding_matrix查找对应的词向量
word_index = tokenizer.word_index   #得到字符串(word)与索引的映射（一般以出现次数作为索引排名的依据，如ChineseNER中用出现次数作为排名，此处应该也是一样）
# print(word_index['hi'])
# print(sequence[2][:20])
print("在所有文本中找到 %s 个单词" % len(word_index))

#生成Train和validate数据集
data = pad_sequences(sequence, maxlen=max_sequence_length)  #对序列进行填充处理,如果不手动设置maxlen，则默认为最长序列的长度
# print("data", data[5], len(data[1]), len(data[5]))
labels = to_categorical(np.asarray(labels)) #将多类别label转换为one-hot向量
# print("label tensor:", labels, type(labels))
indices = np.arange(data.shape[0])
# print(indices)
np.random.shuffle(indices)  #打乱索引顺序
data = data[indices]    #按照打乱的顺序调整data和label，因为原顺序是按照类别排列的，不好划分验证集和训练集
labels = labels[indices]
nb_validation_samples = int(validation_split*data.shape[0]) #验证集数量
x_train = data[:-nb_validation_samples]
# print("x_train", x_train[5])
y_train = labels[:-nb_validation_samples]
# print(x_train.shape)
x_val = data[-nb_validation_samples:]
y_val = labels[-nb_validation_samples:]
print("训练集和验证集已准备好")

#生成词嵌入矩阵（embedding matrix）
#原教程是选择len(word_index)和预设的max_nb_words中的最小值，但是这会导致报错，
# 因为这样会导致embedding_matrix过小，没有包含所有单词的词向量，从而导致报错
nb_words = len(word_index)
embedding_matrix = np.zeros((nb_words+1, embedding_dim))    #为什么要多加一行？
for word, i in word_index.items():
    # if i > max_nb_words:
    #     #只对排名高于max_nb_words的word进行向量初始化，其余的保留为0向量
    #     continue
    #为什么不能用embedding_index[word]获取词向量？因为用get(word)替代[i],遇到key不存在不会报异常，而是返回None
    embedding_vector = embedding_index.get(word)
    if embedding_vector is not None:    #若该词存在于embedding_index中，则初始化，否则保持为0向量
        embedding_matrix[i] = embedding_vector
# print(embedding_matrix[214873])
print(embedding_matrix.shape)
print("embedding_matrix构建完成")

#构建模型
#序列式模型
# embedding_layer = Embedding(nb_words+1,embedding_dim,weights=[embedding_matrix],
#                             input_length=max_sequence_length)
# model = Sequential()
# model.add(embedding_layer)
# model.add(LSTM(100, dropout=0.2))
# #该全连接层的神经元数量是不是太少了？，设置成32、然后activation设置为relu如何？
# model.add(Dense(32, activation='relu'))
# model.add(Dense(len(labels_index), activation='softmax'))
# # model.layers[1].trainable=False #在model.summary中将以训练的参数和未训练的参数区分开？此处参数为词向量
# model.summary()

#函数式模型
#Input的shape是每个样本的维度，每个样本最大长度为1000（每个text1000个单词），而不是每个词的维度，那是下一层的输出
inputs = Input(shape=(None,))
# print(inputs.shape)
word_emb = Embedding(nb_words+1,embedding_dim,weights=[embedding_matrix])(inputs)
# print(word_emb.shape)
lstm = LSTM(100, dropout=0.2)(word_emb)
# print(lstm.shape)
dense = Dense(32, activation='relu')(lstm)
predictions = Dense(len(labels_index), activation='softmax')(dense)
model = Model(inputs=inputs, outputs=predictions)
model.summary()

#训练模型
model.compile(loss='categorical_crossentropy',
              optimizer='adam',
              metrics=['accuracy'])
check_pointer = ModelCheckpoint(filepath='best_model.h5', verbose=1,  save_best_only=True)
print("开始训练。。。")
model.fit(x_train, y_train, batch_size=batch_size, epochs=3,
          validation_data=(x_val, y_val), callbacks=[check_pointer])
# model.save('model_2.h5')
# del model
# model.load_model('model_2.h5')
score, acc = model.evaluate(x_val, y_val, batch_size=batch_size)
print('Test score:', score)
print('Test accuracy:', acc)
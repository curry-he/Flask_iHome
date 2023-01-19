from qiniu import Auth, put_data, etag, urlsafe_base64_encode
import qiniu.config

access_key = '8q8Qz0QD8z3qVZotfftBmUNN1SrrRRVWsfPMDRkt'
secret_key = 'q4RM6MnKdZ23lyx9QM-nT9VVR3Swzfw6gc_Aqdpl'


def storage(file_data):
    q = Auth(access_key, secret_key)

    bucket_name = 'ihome-flask-hhz'

    # 上传到七牛后保存的文件名
    # key = 'my-python-logo.png'

    # 设置转码参数
    fops = 'avthumb/mp4/s/640x360/vb/1.25m'

    # 转码时使用的队列名称
    pipeline = 'abc'

    # 可以对转码后的文件进行使用saveas参数自定义命名，当然也可以不指定文件会默认命名并保存在当前空间
    # saveas_key = urlsafe_base64_encode('目标Bucket_Name:自定义文件key')
    # fops = fops + '|saveas/' + saveas_key

    # 在上传策略中指定
    # policy = {
    #     'persistentOps': fops,
    #     'persistentPipeline': pipeline
    # }

    token = q.upload_token(bucket_name, None, 3600)

    ret, info = put_data(token, None, file_data)

    if info.status_code == 200:
        # 表示上传成功，返回文件名
        return ret.get('key')
    else:
        # 上传失败
        raise Exception('上传七牛失败')

    # print(info)
    # print("*"*10)
    # print(ret)


if __name__ == '__main__':
    with open('28305.jpg', 'rb') as f:
        file_data = f.read()
        file_name = storage(file_data)
        print(file_name)

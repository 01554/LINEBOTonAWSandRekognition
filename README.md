# LINEBOTonAWSLambdaAndRekognition

LINEから画像を送ると AWS の Rekognition に渡して 画像のタグとかくれるものです。
テキストを送ると ドコモ雑談AIに引き渡します。


### install 
```
$ mkdir linebot
$ cd !*
$ wget https://raw.githubusercontent.com/sishinami/LINEBOTonAWSandRekognition/master/lambda_function.py
$ pip install requests -t .
$ zip -r reko *
```

上記で作ったzip を Lambda に UP,
Lambdaがよくわからない人は、Bluprintの microhttp-service で作ってください  
自動的に API Gatewayが選択され、勝手に HTTP end pointが作られます  

画像会席のためには環境変数に 

S3_BUCKET と ACCESS_TOKEN の二つを設定してください。

S3_BUCKET は オレゴンリージョンで作った S3のバケットを

ACCESS_TOKENは LINE Developerから取得できる ACCESS_TOKENです

role には S3と Rekognitionへのアクセス権限を付与してください。

雑談API用に 環境変数に
DOCOMO_APIKEY を設定してください。

後は
LINE Developerに API Gateway のURLを 登録して終わりです

もうちょい解説を増やしました（ドコモとかラインの画面については説明ありません、登録するだけだから！がんばって！）

<http://sysop.hatenablog.com/entry/2017/02/08/190639>







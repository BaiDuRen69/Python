import pandas as pd
import jieba
from snownlp import SnowNLP
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import os


# 设置绘图字体（解决中文乱码问题）
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


# ==========================================
# 1. 数据准备（模拟某电商平台手机评价数据）
# ==========================================
def generate_data():
    data = {
        'review': [
            "手机运行非常流畅，拍照效果绝佳，物流也很快！",
            "屏幕显示清晰，外观时尚，手感很好，非常满意。",
            "性价比很高，电池耐用，充电速度飞快，好评！",
            "整体还算可以，就是系统偶尔会卡顿一下。",
            "一般般吧，没想象中那么好，勉强给个中评。",
            "物流太慢了，包装也有破损，心情很不好。",
            "发热严重，玩游戏没多久就烫手，退货了。",
            "续航能力太差，一天要三充，不推荐购买。",
            "信号非常不稳定，经常断网，体验极差。",
            "刚买回来就降价，客服态度也不行，差评！"
        ]
    }
    df = pd.DataFrame(data)
    # 保存为CSV以便于演示
    df.to_csv('ecommerce_reviews.csv', index=False, encoding='utf-8-sig')
    print(">>> 原始数据已生成并保存为 ecommerce_reviews.csv")
    return df


# ==========================================
# 2. 文本分析与情感计算。
# ==========================================
def analyze_sentiment(df):
    print(">>> 正在进行情感分析...")
    # 计算情感得分 (0.0 到 1.0)
    df['sentiment_score'] = df['review'].apply(lambda x: SnowNLP(x).sentiments)

    # 情感分类：分数 > 0.6 为积极，< 0.4 为消极，中间为中性
    def categorize(score):
        if score > 0.6:
            return '正面'
        elif score < 0.4:
            return '负面'
        else:
            return '中性'

    df['sentiment_type'] = df['sentiment_score'].apply(categorize)
    return df


# ==========================================
# 3. 数据可视化
# ==========================================
def visualize_results(df):
    # 3.1 绘制情感分布饼图
    counts = df['sentiment_type'].value_counts()
    plt.figure(figsize=(8, 6))
    plt.pie(counts, labels=counts.index, autopct='%1.1f%%', colors=['#66b3ff', '#99ff99', '#ff9999'])
    plt.title('电商平台评论情感倾向分布')
    plt.savefig('sentiment_distribution.png')
    plt.show()

    # 3.2 生成关键词词云
    text = " ".join([" ".join(jieba.cut(r)) for r in df['review']])
    wordcloud = WordCloud(
        font_path='simhei.ttf',  # 需确保系统中存在该字体
        background_color='white',
        width=800,
        height=400
    ).generate(text)

    plt.figure(figsize=(10, 5))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    plt.title('用户评价关键词云')
    plt.savefig('wordcloud.png')
    plt.show()


# ==========================================
# 主程序运行
# ==========================================
if __name__ == "__main__":
    # 执行流程
    raw_df = generate_data()
    result_df = analyze_sentiment(raw_df)

    # 输出部分结果到控制台
    print("\n--- 情感分析结果示例 ---")
    print(result_df[['review', 'sentiment_score', 'sentiment_type']])

    # 可视化展示
    visualize_results(result_df)
    print("\n>>> 分析完成！图表已保存为 png 图片。")
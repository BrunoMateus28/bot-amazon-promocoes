import os
import tweepy

def postar_no_twitter(texto):
    """Posta um tweet utilizando a API v2 do Twitter."""
    try:
        client = tweepy.Client(
            consumer_key=os.getenv("TWITTER_API_KEY"),
            consumer_secret=os.getenv("TWITTER_API_SECRET"),
            access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.getenv("TWITTER_ACCESS_SECRET")
        )
        
        response = client.create_tweet(text=texto)
        print(f"Tweet postado com sucesso! ID: {response.data['id']}")
    except Exception as e:
        print(f"Erro ao postar no Twitter: {e}")
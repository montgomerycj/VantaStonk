#!/usr/bin/env python3
"""
Extract tweets from X feed and process through SPS scoring pipeline
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from alerts_logger import AlertsLogger

def sync_x_follows():
    """Sync X follows with SourceWeights tab before processing tweets"""
    try:
        print("🔄 Syncing X follows with SourceWeights...")
        result = subprocess.run(
            ['python3', 'sync_x_follows.py'],
            cwd='/home/ubuntu/kalshibot',
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Check if any new handles were added
            output = result.stdout
            if "Added 0 new handles" in output or "No new handles to add" in output:
                print("✅ X follows sync: No new handles")
            else:
                # Extract number of new handles
                lines = output.split('\n')
                for line in lines:
                    if "Added" in line and "new handles" in line:
                        print(f"✅ X follows sync: {line.strip()}")
                        break
                else:
                    print("✅ X follows sync completed")
        else:
            print(f"⚠️  X follows sync warning: {result.stderr[:100]}")
            
    except subprocess.TimeoutExpired:
        print("⚠️  X follows sync timed out")
    except Exception as e:
        print(f"⚠️  X follows sync error: {str(e)[:100]}")

def extract_tweets_from_feed():
    """Extract the latest 3 tweets from the X Following feed using browser automation"""
    
    try:
        print("🌐 Opening browser to extract real tweets from X Following feed...")
        
        # Use the browser-based tweet extractor
        result = subprocess.run([
            'python3', 'browser_tweet_extractor.py'
        ], cwd='/home/ubuntu/kalshibot', capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and result.stdout.strip():
            import json
            tweets = json.loads(result.stdout.strip())
            print(f"✅ Extracted {len(tweets)} real tweets from X feed")
            
            # Show which accounts we got tweets from
            handles = [tweet['author_handle'] for tweet in tweets]
            print(f"📱 Tweet sources: {', '.join(handles)}")
            
            return tweets
        else:
            print("⚠️  Browser extraction failed, using fallback tweets")
            return get_fallback_tweets()
            
    except Exception as e:
        print(f"❌ Error extracting tweets: {e}")
        print("⚠️  Using fallback tweets")
        return get_fallback_tweets()

def get_fallback_tweets():
    """Fallback tweets in case browser extraction fails"""
    return [
        {
            'text': "Market volatility continues as investors await Fed decision on interest rates",
            'author_handle': '@WSJ',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'tweet_id': 'fallback_wsj_' + str(int(datetime.now().timestamp()))
        },
        {
            'text': "BREAKING: Congressional hearing scheduled on election security measures",
            'author_handle': '@politico',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'tweet_id': 'fallback_politico_' + str(int(datetime.now().timestamp()))
        },
        {
            'text': "New polling data shows tight race in key battleground states",
            'author_handle': '@NateSilver538',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'tweet_id': 'fallback_nate_' + str(int(datetime.now().timestamp()))
        }
    ]

def calculate_sentiment_score(tweet_text):
    """Calculate sentiment score based on tweet content"""
    tweet_lower = tweet_text.lower()
    
    # Bullish indicators
    bullish_words = ['breaking', 'just in', 'announces', 'confirms', 'will', 'solution']
    # Bearish indicators  
    bearish_words = ['cost', 'problem', 'crisis', 'decline', 'fall']
    # Neutral indicators
    neutral_words = ['likely', 'sources say', 'tells', 'said']
    
    bullish_count = sum(1 for word in bullish_words if word in tweet_lower)
    bearish_count = sum(1 for word in bearish_words if word in tweet_lower)
    neutral_count = sum(1 for word in neutral_words if word in tweet_lower)
    
    if bullish_count > bearish_count and bullish_count > neutral_count:
        return 0.7
    elif bearish_count > bullish_count and bearish_count > neutral_count:
        return -0.7
    else:
        return 0.0

def calculate_certainty_score(tweet_text):
    """Calculate certainty score based on language confidence"""
    tweet_lower = tweet_text.lower()
    
    if 'breaking' in tweet_lower or 'just in' in tweet_lower:
        return 1.0
    elif 'confirms' in tweet_lower or 'announces' in tweet_lower:
        return 0.9
    elif 'sources say' in tweet_lower or 'likely' in tweet_lower:
        return 0.6
    elif 'might' in tweet_lower or 'could' in tweet_lower:
        return 0.4
    else:
        return 0.7

def get_source_weight(author_handle):
    """Get source weight from SourceWeights tab"""
    # Updated mapping based on our SourceWeights data including newly added handles
    source_weights = {
        # Original handles
        '@Reuters': 0.8,
        '@Polymarket': 0.4,  # Tier 3 from our data
        '@WSJ': 1.0,  # Tier 1 from our data
        '@JakeSherman': 1.0,  # Tier 1 from our data
        '@politico': 1.0,  # Tier 1 from our data
        '@NickTimiraos': 1.0,  # Tier 1 from our data
        
        # Newly added handles (Tier 1, Weight 0.8)
        '@edokeefe': 0.8,
        '@spectatorindex': 0.8,
        '@epaleezeldin': 0.8,
        '@DailyNewsJustIn': 0.8,
        '@ElectionWiz': 0.8,
        '@ben_d_lazarus': 0.8,
        '@atlas_intel': 0.8,
        '@KobeissiLetter': 0.8,
        '@GRDecter': 0.8,
        '@StealthQE4': 0.8,
        '@PredictIt': 0.8,
        '@cnnbrk': 0.8,
        '@PressSec': 0.8,
        '@SecRubio': 0.8,
        '@LauraLoomer': 0.8,
        
        # Other handles from our follows
        '@jeannasmialek': 0.8,
        '@ZoeTillman': 0.8,
        '@kyledcheney': 0.8,
        '@DemocracyDocket': 0.8,
        '@SCOTUSblog': 0.8,
        '@Redistrict': 0.8,
        '@DecisionDeskHQ': 0.8,
        '@ElectionHQ': 0.8,
        '@simonateba': 0.8,
        '@alerts_chat': 0.8,
        '@Kalshi': 0.8,
        '@kalshiwhales': 0.8,
        '@singsingkix': 0.8,
        '@PolymarktWhales': 0.8,
        '@NateSilver538': 0.8,
        '@RepLuna': 0.8,
        '@nicksortor': 0.8,
        '@realDonaldTrump': 0.8,
        '@RapidResponse47': 0.8,
        '@JudicialWatch': 0.8,
        '@TomFitton': 0.8,
    }
    return source_weights.get(author_handle, 0.5)  # Default for unknown sources

def calculate_similarity_score(tweet_text, contract_title):
    """Calculate similarity score (simplified for demo)"""
    tweet_lower = tweet_text.lower()
    title_lower = contract_title.lower()
    
    # Simple keyword matching for demo
    if 'fed' in tweet_lower and 'fed' in title_lower:
        return 0.85
    elif 'trump' in tweet_lower and 'trump' in title_lower:
        return 0.90
    elif 'biden' in tweet_lower and 'biden' in title_lower:
        return 0.90
    elif 'oil' in tweet_lower and ('energy' in title_lower or 'oil' in title_lower):
        return 0.75
    else:
        return 0.3  # Low similarity

def calculate_sps_score(source_weight, sentiment_score, certainty_score, similarity_score):
    """Calculate SPS score using the specified formula"""
    sps = (0.25 * source_weight) + \
          (0.20 * sentiment_score) + \
          (0.20 * certainty_score) + \
          (0.20 * similarity_score) + \
          (0.15 * 0.70)  # Static momentum
    return round(sps, 3)

def process_tweets_through_sps():
    """Process extracted tweets through SPS scoring pipeline"""
    
    # First, sync X follows with SourceWeights
    sync_x_follows()
    
    print("🐦 Extracting tweets from X Following feed...")
    tweets = extract_tweets_from_feed()
    
    print(f"📊 Found {len(tweets)} tweets to process")
    
    # Sample contracts from WatchlistContracts (simplified for demo)
    contracts = [
        {'ticker': 'KXDJTPARAMOUNT-25', 'title': 'DJ Trump Paramount related contract'},
        {'ticker': 'KXFOMCDISSENTCOUNT-25JUL-2', 'title': 'Fed FOMC dissent count 2 dissents'},
        {'ticker': 'KXTRUMPSAYMAM-25AUG-AGU', 'title': 'Trump Manafort related contract'},
    ]
    
    alerts_logger = AlertsLogger()
    alerts_generated = 0
    
    for tweet in tweets:
        print(f"\n🔍 Processing tweet from {tweet['author_handle']}:")
        print(f"   Text: {tweet['text'][:100]}...")
        
        source_weight = get_source_weight(tweet['author_handle'])
        sentiment_score = calculate_sentiment_score(tweet['text'])
        certainty_score = calculate_certainty_score(tweet['text'])
        
        print(f"   Source Weight: {source_weight}")
        print(f"   Sentiment: {sentiment_score}")
        print(f"   Certainty: {certainty_score}")
        
        # Track if this tweet generated any alerts
        tweet_generated_alert = False
        best_match = None
        best_sps_score = 0
        
        # Check against each contract
        for contract in contracts:
            similarity_score = calculate_similarity_score(tweet['text'], contract['title'])
            
            if similarity_score >= 0.70:  # Similarity threshold
                sps_score = calculate_sps_score(source_weight, sentiment_score, certainty_score, similarity_score)
                
                print(f"   📈 Match found with {contract['ticker']}:")
                print(f"      Similarity: {similarity_score}")
                print(f"      SPS Score: {sps_score}")
                
                # Track best match for No Action logging
                if sps_score > best_sps_score:
                    best_sps_score = sps_score
                    best_match = {
                        'contract_ticker': contract['ticker'],
                        'contract_title': contract['title'],
                        'similarity_score': similarity_score,
                        'sps_score': sps_score
                    }
                
                if sps_score >= 0.70:  # SPS threshold for alerts
                    # Check if recently alerted
                    if not alerts_logger.check_recent_alerts(contract['ticker'], hours=6):
                        # Generate alert
                        alert_data = {
                            'tweet_id': tweet['tweet_id'],
                            'contract_ticker': contract['ticker'],
                            'sps_score': sps_score,
                            'similarity_score': similarity_score,
                            'sentiment_score': sentiment_score,
                            'certainty_score': certainty_score,
                            'source_weight': source_weight,
                            'username': tweet['author_handle'],
                            'tweet_text': tweet['text']
                        }
                        
                        success = alerts_logger.log_alert(alert_data)
                        if success:
                            alerts_generated += 1
                            tweet_generated_alert = True
                            print(f"      🚨 ALERT GENERATED!")
                        else:
                            print(f"      ❌ Alert logging failed")
                    else:
                        print(f"      ⏭️  Skipped - recently alerted")
                        # Still log to No Action since no new alert was generated
                else:
                    print(f"      ⚠️  SPS below alert threshold (0.70)")
            else:
                print(f"   ⏭️  Low similarity with {contract['ticker']}: {similarity_score}")
        
        # Log to No Action tab if no alert was generated
        if not tweet_generated_alert:
            # Prepare data for No Action logging
            no_action_data = {
                'tweet_id': tweet['tweet_id'],
                'username': tweet['author_handle'],
                'tweet_text': tweet['text'],
                'source_weight': source_weight,
                'sentiment_score': sentiment_score,
                'certainty_score': certainty_score
            }
            
            # Add best match info if available
            if best_match:
                no_action_data.update({
                    'contract_ticker': best_match['contract_ticker'],
                    'contract_title': best_match['contract_title'],
                    'similarity_score': best_match['similarity_score'],
                    'sps_score': best_match['sps_score']
                })
                reason = f"SPS {best_match['sps_score']:.3f} below 0.70 threshold"
            else:
                no_action_data.update({
                    'contract_ticker': '',
                    'contract_title': '',
                    'similarity_score': '',
                    'sps_score': ''
                })
                reason = "No contract similarity above 0.70"
            
            # Log to No Action tab
            alerts_logger.log_no_action(no_action_data, reason)
    
    print(f"\n🎉 Processing complete!")
    print(f"   Tweets processed: {len(tweets)}")
    print(f"   Alerts generated: {alerts_generated}")
    
    return tweets, alerts_generated

if __name__ == "__main__":
    print("Kalshibot Tweet Processing Pipeline")
    print("=" * 40)
    process_tweets_through_sps()


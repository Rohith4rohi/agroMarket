# market_price_service.py
import requests
import json
from datetime import datetime, timedelta
import random

class MarketPriceService:
    """Service to fetch real-time market prices for agricultural products"""
    
    def __init__(self):
        # Database of commodity codes for different APIs
        self.commodity_codes = {
            'Wheat': {'name': 'Wheat', 'code': 'WHT', 'mandi_name': 'Wheat'},
            'Rice': {'name': 'Rice', 'code': 'RICE', 'mandi_name': 'Rice'},
            'Maize': {'name': 'Maize', 'code': 'CORN', 'mandi_name': 'Maize'},
            'Soybean': {'name': 'Soybean', 'code': 'SOYB', 'mandi_name': 'Soybean'},
            'Cotton': {'name': 'Cotton', 'code': 'COTTON', 'mandi_name': 'Cotton'},
            'Sugarcane': {'name': 'Sugarcane', 'code': 'SUGAR', 'mandi_name': 'Sugarcane'},
            'Tomato': {'name': 'Tomato', 'code': 'TOMATO', 'mandi_name': 'Tomato'},
            'Onion': {'name': 'Onion', 'code': 'ONION', 'mandi_name': 'Onion'},
            'Potato': {'name': 'Potato', 'code': 'POTATO', 'mandi_name': 'Potato'},
            'Apple': {'name': 'Apple', 'code': 'APPLE', 'mandi_name': 'Apple'},
            'Mango': {'name': 'Mango', 'code': 'MANGO', 'mandi_name': 'Mango'},
            'Banana': {'name': 'Banana', 'code': 'BANANA', 'mandi_name': 'Banana'},
            'Grapes': {'name': 'Grapes', 'code': 'GRAPES', 'mandi_name': 'Grapes'},
            'Orange': {'name': 'Orange', 'code': 'ORANGE', 'mandi_name': 'Orange'},
            'Milk': {'name': 'Milk', 'code': 'MILK', 'mandi_name': 'Milk'},
        }
        
        # Cache for market prices (to avoid too many API calls)
        self.price_cache = {}
        self.cache_duration = 3600  # 1 hour cache
        
    def get_market_price(self, commodity, location="National"):
        """Get market price for a commodity"""
        
        # Check cache first
        cache_key = f"{commodity}_{location}"
        if cache_key in self.price_cache:
            cached_data = self.price_cache[cache_key]
            if datetime.now() - cached_data['timestamp'] < timedelta(seconds=self.cache_duration):
                return cached_data['data']
        
        # Try to fetch from different sources
        price_data = self._fetch_from_api(commodity, location)
        
        if not price_data:
            # Fallback to simulated data based on real market trends
            price_data = self._get_simulated_price(commodity)
        
        # Cache the result
        self.price_cache[cache_key] = {
            'data': price_data,
            'timestamp': datetime.now()
        }
        
        return price_data
    
    def _fetch_from_api(self, commodity, location):
        """Fetch real market price from API"""
        try:
            # Convert commodity to API-friendly name
            commodity_info = self.commodity_codes.get(commodity, {'name': commodity, 'code': commodity.upper()})
            
            # Using a free commodity price API (you can replace with actual API)
            # Example: Using data.gov.in API for Indian mandi prices (requires API key)
            # For demo, we'll use a mock API response
            
            # In production, you would use actual APIs like:
            # - data.gov.in (Indian market prices)
            # - agmarknet.gov.in
            # - worldbank.org commodity prices
            # - alphavantage.co
            
            # Sample API call structure:
            # response = requests.get(f"https://api.data.gov.in/resource/your-resource-id?api-key=YOUR_KEY&format=json&filters[commodity]={commodity_info['code']}")
            # if response.status_code == 200:
            #     data = response.json()
            #     return self._parse_api_response(data)
            
            # For now, return None to use simulated data
            return None
            
        except Exception as e:
            print(f"Error fetching market price from API: {e}")
            return None
    
    def _get_simulated_price(self, commodity):
        """Generate simulated market price based on real market trends"""
        
        # Base prices for different commodities (in Rs per kg)
        base_prices = {
            'Vegetables': {'Tomato': 40, 'Onion': 35, 'Potato': 30, 'Cabbage': 25, 'Cauliflower': 35, 'Brinjal': 40, 'Ladyfinger': 45},
            'Fruits': {'Apple': 120, 'Mango': 80, 'Banana': 40, 'Orange': 60, 'Grapes': 70, 'Pomegranate': 100},
            'Grains': {'Wheat': 25, 'Rice': 35, 'Maize': 20, 'Barley': 22, 'Millet': 30},
            'Pulses': {'Toor Dal': 100, 'Moong Dal': 90, 'Masoor Dal': 80, 'Chana Dal': 85},
            'Spices': {'Turmeric': 150, 'Cumin': 200, 'Coriander': 70, 'Red Chili': 180},
            'Oilseeds': {'Soybean': 60, 'Groundnut': 70, 'Sunflower': 80, 'Mustard': 75},
            'Dairy': {'Milk': 50, 'Curd': 60, 'Butter': 400, 'Cheese': 500},
        }
        
        # Find the commodity price
        price = None
        for category, items in base_prices.items():
            if commodity in items:
                price = items[commodity]
                break
        
        if not price:
            # Default price if commodity not found
            price = 50
        
        # Add some random variation (market fluctuations)
        variation = random.uniform(-0.1, 0.15)  # -10% to +15%
        current_price = price * (1 + variation)
        
        # Calculate price trends (up/down/stable)
        trend = random.choice(['up', 'down', 'stable'])
        trend_percent = random.uniform(0.5, 5) if trend != 'stable' else 0
        
        # Determine market sentiment
        if current_price > price * 1.1:
            sentiment = "bullish"
        elif current_price < price * 0.9:
            sentiment = "bearish"
        else:
            sentiment = "stable"
        
        return {
            'commodity': commodity,
            'price': round(current_price, 2),
            'unit': 'kg',
            'currency': 'INR',
            'trend': trend,
            'trend_percent': round(trend_percent, 2),
            'sentiment': sentiment,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'source': 'Market Analysis',
            'confidence': 'medium',
            'week_high': round(price * 1.15, 2),
            'week_low': round(price * 0.85, 2),
            'volume': random.randint(1000, 10000),
            'location': 'National Market'
        }
    
    def get_price_for_category(self, category, specific_commodity=None):
        """Get market price for a category"""
        category_prices = {
            'Vegetables': 35,
            'Fruits': 70,
            'Grains': 25,
            'Pulses': 85,
            'Spices': 150,
            'Oilseeds': 65,
            'Dairy': 50,
            'Others': 100
        }
        
        base_price = category_prices.get(category, 50)
        
        # Add random variation
        variation = random.uniform(-0.15, 0.2)
        current_price = base_price * (1 + variation)
        
        trend = random.choice(['up', 'down', 'stable'])
        
        return {
            'category': category,
            'price': round(current_price, 2),
            'unit': 'kg',
            'trend': trend,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def get_multiple_prices(self, commodities):
        """Get market prices for multiple commodities"""
        prices = {}
        for commodity in commodities:
            prices[commodity] = self.get_market_price(commodity)
        return prices
    
    def compare_with_market(self, product_price, commodity):
        """Compare product price with market price"""
        market_data = self.get_market_price(commodity)
        
        if market_data:
            market_price = market_data['price']
            difference = product_price - market_price
            percent_diff = (difference / market_price) * 100
            
            if percent_diff < -10:
                recommendation = "Price is below market rate. Consider increasing for better profit."
                status = "undervalued"
            elif percent_diff > 10:
                recommendation = "Price is above market rate. May affect competitiveness."
                status = "overvalued"
            else:
                recommendation = "Price is competitive with current market rates."
                status = "competitive"
            
            return {
                'market_price': market_price,
                'product_price': product_price,
                'difference': round(difference, 2),
                'percent_diff': round(percent_diff, 2),
                'recommendation': recommendation,
                'status': status,
                'trend': market_data.get('trend', 'stable')
            }
        
        return None

# Create a singleton instance
market_price_service = MarketPriceService()
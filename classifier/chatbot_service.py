"""
Chatbot Service - Xử lý hỏi đáp về giống chó, giá cả, thông tin cửa hàng
"""
import re
from django.db.models import Q, Min, Max, Avg
from .models import DogBreed, Dog


class ChatbotService:
    """Service xử lý logic chatbot"""
    
    # Các từ khóa nhận diện intent
    BREED_KEYWORDS = ['giống', 'loại', 'breed', 'species', 'chủng']
    PRICE_KEYWORDS = ['giá', 'bao nhiêu tiền', 'price', 'cost', 'đắt', 'rẻ']
    CHARACTERISTIC_KEYWORDS = ['đặc điểm', 'đặc tính', 'tính cách', 'characteristic', 'feature', 'như thế nào', 'ra sao']
    ORIGIN_KEYWORDS = ['xuất xứ', 'nguồn gốc', 'origin', 'từ đâu', 'nước nào']
    AVAILABLE_KEYWORDS = ['còn', 'có', 'bán', 'available', 'mua được']
    GREETING_KEYWORDS = ['xin chào', 'hello', 'hi', 'chào', 'hey', 'alo']
    HELP_KEYWORDS = ['giúp', 'help', 'hỗ trợ', 'hướng dẫn', 'làm sao', 'cách nào']
    LIST_KEYWORDS = ['danh sách', 'list', 'tất cả', 'những', 'các loại', 'có những gì']
    LIST_DOGS_KEYWORDS = ['con nào', 'chó nào', 'những con', 'các con', 'liệt kê', 'xem chó', 'chó đang bán', 'con chó']
    DOG_INFO_KEYWORDS = ['thông tin', 'chi tiết', 'info', 'detail', 'về con']
    
    # Alias cho các tên giống phổ biến
    BREED_ALIASES = {
        'corgi': ['pembroke', 'cardigan', 'welsh corgi'],
        'husky': ['siberian husky', 'siberian_husky'],
        'golden': ['golden retriever', 'golden_retriever'],
        'poodle': ['toy poodle', 'miniature poodle', 'standard poodle'],
        'bulldog': ['french bulldog', 'english bulldog', 'bull_mastiff'],
        'shepherd': ['german shepherd', 'german_shepherd'],
        'retriever': ['golden retriever', 'labrador retriever'],
        'lab': ['labrador', 'labrador_retriever'],
        'shiba': ['shiba inu', 'shiba_inu'],
        'dachshund': ['dachshund'],
        'beagle': ['beagle'],
        'pug': ['pug'],
        'chihuahua': ['chihuahua'],
        'doberman': ['doberman', 'doberman pinscher'],
        'rottweiler': ['rottweiler'],
        'boxer': ['boxer'],
        'schnauzer': ['miniature schnauzer', 'standard schnauzer', 'giant schnauzer'],
    }
    
    def __init__(self):
        self.breed_names = list(DogBreed.objects.values_list('name', flat=True))
    
    def process_message(self, message: str) -> dict:
        """
        Xử lý tin nhắn và trả về response
        
        Args:
            message: Tin nhắn từ user
            
        Returns:
            dict với keys: response, intent, data
        """
        message_lower = message.lower().strip()
        
        # Xác định intent
        intent = self._detect_intent(message_lower)
        
        # Xử lý theo intent
        if intent == 'greeting':
            return self._handle_greeting()
        elif intent == 'help':
            return self._handle_help()
        elif intent == 'list_breeds':
            return self._handle_list_breeds()
        elif intent == 'list_dogs':
            return self._handle_list_dogs(message_lower)
        elif intent == 'dog_info':
            return self._handle_dog_info(message_lower)
        elif intent == 'breed_info':
            return self._handle_breed_info(message_lower)
        elif intent == 'price_query':
            return self._handle_price_query(message_lower)
        elif intent == 'characteristic':
            return self._handle_characteristic(message_lower)
        elif intent == 'origin':
            return self._handle_origin(message_lower)
        elif intent == 'availability':
            return self._handle_availability(message_lower)
        else:
            return self._handle_unknown(message_lower)
    
    def _detect_intent(self, message: str) -> str:
        """Nhận diện intent từ tin nhắn"""
        
        # Greeting
        if any(kw in message for kw in self.GREETING_KEYWORDS):
            return 'greeting'
        
        # Help
        if any(kw in message for kw in self.HELP_KEYWORDS) and len(message) < 30:
            return 'help'
        
        # List all breeds
        if any(kw in message for kw in self.LIST_KEYWORDS) and any(kw in message for kw in self.BREED_KEYWORDS):
            return 'list_breeds'
        
        # List dogs for sale
        if any(kw in message for kw in self.LIST_DOGS_KEYWORDS):
            return 'list_dogs'
        
        # Dog info - thông tin chi tiết về 1 con chó
        if any(kw in message for kw in self.DOG_INFO_KEYWORDS) and self._find_dog_in_message(message):
            return 'dog_info'
        
        # Price query
        if any(kw in message for kw in self.PRICE_KEYWORDS):
            return 'price_query'
        
        # Characteristics
        if any(kw in message for kw in self.CHARACTERISTIC_KEYWORDS):
            return 'characteristic'
        
        # Origin
        if any(kw in message for kw in self.ORIGIN_KEYWORDS):
            return 'origin'
        
        # Availability check
        if any(kw in message for kw in self.AVAILABLE_KEYWORDS):
            return 'availability'
        
        # Check if asking about a specific dog by name
        if self._find_dog_in_message(message):
            return 'dog_info'
        
        # Check if asking about a specific breed
        if self._find_breed_in_message(message):
            return 'breed_info'
        
        return 'unknown'
    
    def _find_breed_in_message(self, message: str) -> DogBreed:
        """Tìm giống chó được đề cập trong tin nhắn"""
        breeds = DogBreed.objects.all()
        
        # Đầu tiên, check alias mapping
        for alias, breed_names in self.BREED_ALIASES.items():
            if alias in message:
                # Tìm breed matching với alias
                for breed in breeds:
                    breed_name_lower = breed.name.lower().replace('_', ' ')
                    if any(bn in breed_name_lower or breed_name_lower in bn for bn in breed_names):
                        return breed
                    # Nếu alias trùng với một phần tên breed
                    if alias in breed_name_lower:
                        return breed
        
        # Sau đó match trực tiếp
        for breed in breeds:
            breed_name_lower = breed.name.lower()
            # Match tên đầy đủ
            if breed_name_lower in message or breed_name_lower.replace('_', ' ') in message:
                return breed
            # Match từng từ trong tên giống (> 3 ký tự)
            words = breed_name_lower.replace('_', ' ').split()
            if any(word in message and len(word) > 3 for word in words):
                return breed
        
        return None
    
    def _find_dog_in_message(self, message: str) -> Dog:
        """Tìm chó cụ thể được đề cập trong tin nhắn (theo tên)"""
        dogs = Dog.objects.filter(is_available=True).select_related('breed')
        for dog in dogs:
            dog_name_lower = dog.name.lower()
            if dog_name_lower in message:
                return dog
        return None
    
    def _handle_greeting(self) -> dict:
        return {
            'response': (
                "🐕 Xin chào! Tôi là trợ lý ảo của DogShop.\n\n"
                "Tôi có thể giúp bạn:\n"
                "• Tìm hiểu về các giống chó\n"
                "• Tra cứu giá cả\n"
                "• Kiểm tra chó còn bán\n"
                "• Xem đặc điểm, xuất xứ của từng giống\n"
                "• Xem danh sách chó đang bán\n\n"
                "Hãy hỏi tôi bất cứ điều gì!"
            ),
            'intent': 'greeting',
            'data': None
        }
    
    def _handle_help(self) -> dict:
        return {
            'response': (
                "Hướng dẫn sử dụng chatbot:\n\n"
                "Bạn có thể hỏi:\n"
                "• \"Danh sách các giống chó\" - Xem tất cả giống\n"
                "• \"Chó nào đang bán?\" - Xem danh sách chó\n"
                "• \"Thông tin về Lucky\" - Chi tiết 1 con chó\n"
                "• \"Golden Retriever giá bao nhiêu?\" - Hỏi giá\n"
                "• \"Đặc điểm của Husky\" - Xem tính cách\n"
                "• \"Có chó Corgi không?\" - Kiểm tra còn hàng\n\n"
                "Gõ tên chó hoặc giống chó để xem chi tiết!"
            ),
            'intent': 'help',
            'data': None
        }
    
    def _handle_list_breeds(self) -> dict:
        breeds = DogBreed.objects.all()
        breeds_with_count = []
        
        for breed in breeds:
            available_count = Dog.objects.filter(breed=breed, is_available=True).count()
            breeds_with_count.append({
                'id': breed.id,
                'name': breed.name,
                'available_count': available_count
            })
        
        if not breeds_with_count:
            return {
                'response': "Hiện tại chưa có giống chó nào trong hệ thống.",
                'intent': 'list_breeds',
                'data': []
            }
        
        response = "Các giống chó tại DogShop:\n\n"
        for b in breeds_with_count:
            status = f"({b['available_count']} chó đang bán)" if b['available_count'] > 0 else "(Hết hàng)"
            response += f"• {b['name']} {status}\n"
        
        response += f"\nTổng cộng: {len(breeds_with_count)} giống chó"
        
        return {
            'response': response,
            'intent': 'list_breeds',
            'data': breeds_with_count
        }
    
    def _handle_list_dogs(self, message: str) -> dict:
        """Liệt kê tất cả chó đang bán hoặc theo giống"""
        breed = self._find_breed_in_message(message)
        
        if breed:
            dogs = Dog.objects.filter(breed=breed, is_available=True).select_related('breed')
        else:
            dogs = Dog.objects.filter(is_available=True).select_related('breed')
        
        if not dogs.exists():
            if breed:
                return {
                    'response': f"Hiện không có {breed.name} nào đang bán.",
                    'intent': 'list_dogs',
                    'data': {'breed_name': breed.name, 'dogs': []}
                }
            return {
                'response': "Hiện không có chó nào đang bán.",
                'intent': 'list_dogs',
                'data': {'dogs': []}
            }
        
        if breed:
            response = f"Danh sách {breed.name} đang bán ({dogs.count()} con):\n\n"
        else:
            response = f"Danh sách chó đang bán ({dogs.count()} con):\n\n"
        
        dogs_data = []
        for i, dog in enumerate(dogs[:10], 1):
            age_str = f"{dog.age_months} tháng" if dog.age_months < 12 else f"{dog.age_months // 12} tuổi {dog.age_months % 12} tháng"
            response += f"{i}. **{dog.name}** - {dog.breed.name}\n"
            response += f"   {age_str} | {dog.color}\n"
            response += f"   {self._format_price(dog.price)}\n\n"
            
            dogs_data.append({
                'id': dog.id,
                'name': dog.name,
                'breed': dog.breed.name,
                'age_months': dog.age_months,
                'color': dog.color,
                'price': float(dog.price),
                'description': dog.description
            })
        
        if dogs.count() > 10:
            response += f"... và {dogs.count() - 10} chó khác\n"
        
        response += "\nGõ tên chó để xem chi tiết. VD: \"Thông tin về Lucky\""
        
        return {
            'response': response,
            'intent': 'list_dogs',
            'data': {
                'breed_name': breed.name if breed else None,
                'total': dogs.count(),
                'dogs': dogs_data
            }
        }
    
    def _handle_dog_info(self, message: str) -> dict:
        """Thông tin chi tiết về một con chó cụ thể"""
        dog = self._find_dog_in_message(message)
        
        if not dog:
            return {
                'response': (
                    "Không tìm thấy chó với tên này.\n\n"
                    "Gõ \"Xem chó đang bán\" để xem danh sách."
                ),
                'intent': 'dog_info',
                'data': None
            }
        
        age_str = f"{dog.age_months} tháng" if dog.age_months < 12 else f"{dog.age_months // 12} tuổi {dog.age_months % 12} tháng"
        
        response = f" Thông tin chi tiết về {dog.name}:\n\n"
        response += f" **Giống:** {dog.breed.name}\n"
        response += f" **Tuổi:** {age_str}\n"
        response += f" **Màu sắc:** {dog.color}\n"
        response += f" **Giá:** {self._format_price(dog.price)}\n"
        
        if dog.description:
            response += f"\n **Mô tả:** {dog.description}\n"
        
        # Thêm thông tin giống chó
        if dog.breed.characteristics:
            response += f"\n **Đặc điểm giống {dog.breed.name}:**\n{dog.breed.characteristics}\n"
        
        if dog.breed.origin:
            response += f"\n **Xuất xứ:** {dog.breed.origin}\n"
        
        response += f"\n Truy cập website để đặt mua {dog.name}!"
        
        return {
            'response': response,
            'intent': 'dog_info',
            'data': {
                'id': dog.id,
                'name': dog.name,
                'breed': {
                    'id': dog.breed.id,
                    'name': dog.breed.name,
                    'characteristics': dog.breed.characteristics,
                    'origin': dog.breed.origin
                },
                'age_months': dog.age_months,
                'color': dog.color,
                'price': float(dog.price),
                'description': dog.description,
                'is_available': dog.is_available
            }
        }
    
    def _handle_breed_info(self, message: str) -> dict:
        breed = self._find_breed_in_message(message)
        
        if not breed:
            return self._handle_unknown(message)
        
        # Lấy thông tin giá từ các chó đang bán
        dogs = Dog.objects.filter(breed=breed, is_available=True)
        price_info = dogs.aggregate(
            min_price=Min('price'),
            max_price=Max('price'),
            avg_price=Avg('price')
        )
        
        response = f" Thông tin về {breed.name}:\n\n"
        
        if breed.description:
            response += f" Mô tả: {breed.description}\n\n"
        
        if breed.characteristics:
            response += f" Đặc điểm: {breed.characteristics}\n\n"
        
        if breed.origin:
            response += f" Xuất xứ: {breed.origin}\n\n"
        
        if dogs.exists():
            response += f" Giá: {self._format_price(price_info['min_price'])}"
            if price_info['min_price'] != price_info['max_price']:
                response += f" - {self._format_price(price_info['max_price'])}"
            response += f"\n Hiện có: {dogs.count()} chó đang bán"
        else:
            response += " Hiện không có chó giống này đang bán"
        
        return {
            'response': response,
            'intent': 'breed_info',
            'data': {
                'breed_id': breed.id,
                'breed_name': breed.name,
                'description': breed.description,
                'characteristics': breed.characteristics,
                'origin': breed.origin,
                'available_count': dogs.count(),
                'price_range': {
                    'min': float(price_info['min_price']) if price_info['min_price'] else None,
                    'max': float(price_info['max_price']) if price_info['max_price'] else None,
                }
            }
        }
    
    def _handle_price_query(self, message: str) -> dict:
        breed = self._find_breed_in_message(message)
        
        if breed:
            dogs = Dog.objects.filter(breed=breed, is_available=True)
            
            if dogs.exists():
                price_info = dogs.aggregate(
                    min_price=Min('price'),
                    max_price=Max('price')
                )
                
                if price_info['min_price'] == price_info['max_price']:
                    response = f"Giá {breed.name}: {self._format_price(price_info['min_price'])}"
                else:
                    response = (
                        f"Giá {breed.name}:\n"
                        f"• Thấp nhất: {self._format_price(price_info['min_price'])}\n"
                        f"• Cao nhất: {self._format_price(price_info['max_price'])}\n\n"
                        f"Hiện có {dogs.count()} chó đang bán"
                    )
                
                # Liệt kê một vài con cụ thể
                dog_list = dogs[:3]
                if dog_list:
                    response += "\n\n Chi tiết:\n"
                    for dog in dog_list:
                        response += f"• {dog.name} ({dog.age_months} tháng tuổi): {self._format_price(dog.price)}\n"
                
                return {
                    'response': response,
                    'intent': 'price_query',
                    'data': {
                        'breed_name': breed.name,
                        'min_price': float(price_info['min_price']),
                        'max_price': float(price_info['max_price']),
                        'count': dogs.count()
                    }
                }
            else:
                return {
                    'response': f" Hiện không có {breed.name} đang bán. Vui lòng quay lại sau!",
                    'intent': 'price_query',
                    'data': {'breed_name': breed.name, 'available': False}
                }
        
        # Nếu không tìm thấy giống cụ thể, show giá chung
        all_dogs = Dog.objects.filter(is_available=True)
        if all_dogs.exists():
            price_info = all_dogs.aggregate(
                min_price=Min('price'),
                max_price=Max('price')
            )
            return {
                'response': (
                    f" Giá chó tại DogShop:\n"
                    f"• Thấp nhất: {self._format_price(price_info['min_price'])}\n"
                    f"• Cao nhất: {self._format_price(price_info['max_price'])}\n\n"
                    f" Hiện có {all_dogs.count()} chó đang bán.\n\n"
                    f" Để biết giá cụ thể, hãy hỏi theo giống chó. Ví dụ: \"Giá Golden Retriever\""
                ),
                'intent': 'price_query',
                'data': {
                    'min_price': float(price_info['min_price']),
                    'max_price': float(price_info['max_price']),
                    'total_count': all_dogs.count()
                }
            }
        
        return {
            'response': " Hiện không có chó nào đang bán.",
            'intent': 'price_query',
            'data': None
        }
    
    def _handle_characteristic(self, message: str) -> dict:
        breed = self._find_breed_in_message(message)
        
        if breed:
            if breed.characteristics:
                return {
                    'response': f" Đặc điểm của {breed.name}:\n\n{breed.characteristics}",
                    'intent': 'characteristic',
                    'data': {
                        'breed_name': breed.name,
                        'characteristics': breed.characteristics
                    }
                }
            else:
                return {
                    'response': f" Chưa có thông tin đặc điểm chi tiết về {breed.name}.",
                    'intent': 'characteristic',
                    'data': {'breed_name': breed.name}
                }
        
        return {
            'response': (
                " Bạn muốn biết đặc điểm của giống chó nào?\n\n"
                " Ví dụ: \"Đặc điểm của Husky\" hoặc \"Golden Retriever như thế nào?\""
            ),
            'intent': 'characteristic',
            'data': None
        }
    
    def _handle_origin(self, message: str) -> dict:
        breed = self._find_breed_in_message(message)
        
        if breed:
            if breed.origin:
                return {
                    'response': f" Xuất xứ của {breed.name}: {breed.origin}",
                    'intent': 'origin',
                    'data': {
                        'breed_name': breed.name,
                        'origin': breed.origin
                    }
                }
            else:
                return {
                    'response': f" Chưa có thông tin xuất xứ về {breed.name}.",
                    'intent': 'origin',
                    'data': {'breed_name': breed.name}
                }
        
        return {
            'response': (
                " Bạn muốn biết xuất xứ của giống chó nào?\n\n"
                " Ví dụ: \"Poodle xuất xứ từ đâu?\" hoặc \"Nguồn gốc của Corgi\""
            ),
            'intent': 'origin',
            'data': None
        }
    
    def _handle_availability(self, message: str) -> dict:
        breed = self._find_breed_in_message(message)
        
        if breed:
            dogs = Dog.objects.filter(breed=breed, is_available=True)
            
            if dogs.exists():
                response = f"✅ Có! Hiện có {dogs.count()} {breed.name} đang bán:\n\n"
                for dog in dogs[:5]:
                    age_str = f"{dog.age_months} tháng" if dog.age_months < 12 else f"{dog.age_months // 12} tuổi"
                    response += f"• {dog.name} - {age_str} - {dog.color} - {self._format_price(dog.price)}\n"
                
                if dogs.count() > 5:
                    response += f"\n... và {dogs.count() - 5} chó khác"
                
                response += "\n\n Gõ tên chó để xem chi tiết!"
                
                return {
                    'response': response,
                    'intent': 'availability',
                    'data': {
                        'breed_name': breed.name,
                        'available': True,
                        'count': dogs.count(),
                        'dogs': [{'id': d.id, 'name': d.name, 'price': float(d.price)} for d in dogs[:5]]
                    }
                }
            else:
                # Breed exists but no dogs available
                return {
                    'response': f" Rất tiếc, hiện không có {breed.name} đang bán. Hãy quay lại sau nhé!",
                    'intent': 'availability',
                    'data': {'breed_name': breed.name, 'available': False}
                }
        
        # Không tìm thấy breed - có thể user hỏi giống không có trong DB
        # Tìm từ khóa giống trong message
        asked_breed = self._extract_breed_keyword(message)
        
        total_dogs = Dog.objects.filter(is_available=True).count()
        breeds_with_dogs = DogBreed.objects.filter(
            dogs__is_available=True
        ).distinct()
        
        if asked_breed:
            # User hỏi về giống cụ thể nhưng không có trong DB
            if breeds_with_dogs.exists():
                breed_list = ", ".join([b.name for b in breeds_with_dogs[:8]])
                response = (
                    f" Rất tiếc, hiện không có giống \"{asked_breed}\" trong cửa hàng.\n\n"
                    f" Các giống đang bán ({total_dogs} chó):\n{breed_list}\n\n"
                    f" Bạn có muốn xem giống khác không?"
                )
            else:
                response = f" Hiện không có giống \"{asked_breed}\" và cũng không có chó nào đang bán."
        else:
            # User hỏi chung
            if breeds_with_dogs.exists():
                breed_list = ", ".join([b.name for b in breeds_with_dogs[:10]])
                response = (
                    f" DogShop hiện có {total_dogs} chó đang bán:\n\n"
                    f" Các giống: {breed_list}\n\n"
                    f" Hỏi cụ thể: \"Có chó {breeds_with_dogs.first().name} không?\""
                )
            else:
                response = " Hiện không có chó nào đang bán."
        
        return {
            'response': response,
            'intent': 'availability',
            'data': {
                'asked_breed': asked_breed,
                'total_dogs': total_dogs,
                'total_breeds': breeds_with_dogs.count(),
                'breeds': [b.name for b in breeds_with_dogs]
            }
        }
    
    def _extract_breed_keyword(self, message: str) -> str:
        """Trích xuất từ khóa giống chó từ message (dù không match DB)"""
        # Các pattern phổ biến
        import re
        
        # Pattern: "có chó X không", "còn X không", "có X không"
        patterns = [
            r'có chó\s+(\w+)',
            r'còn chó\s+(\w+)',
            r'có\s+(\w+)\s+không',
            r'còn\s+(\w+)\s+không',
            r'chó\s+(\w+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                word = match.group(1)
                # Loại bỏ các từ không phải tên giống
                if word not in ['nào', 'gì', 'con', 'đang', 'bán', 'được', 'mua']:
                    return word.title()
        
        # Check alias keys
        for alias in self.BREED_ALIASES.keys():
            if alias in message:
                return alias.title()
        
        return None
    
    def _handle_unknown(self, message: str) -> dict:
        # Cố gắng tìm giống chó trong message
        breed = self._find_breed_in_message(message)
        if breed:
            return self._handle_breed_info(message)
        
        return {
            'response': (
                " Tôi chưa hiểu câu hỏi của bạn.\n\n"
                "Bạn có thể thử:\n"
                "• \"Danh sách các giống chó\"\n"
                "• \"Giá Golden Retriever\"\n"
                "• \"Đặc điểm của Husky\"\n"
                "• \"Có chó Corgi không?\"\n\n"
                "Hoặc gõ \"help\" để xem hướng dẫn chi tiết."
            ),
            'intent': 'unknown',
            'data': None
        }
    
    def _format_price(self, price) -> str:
        """Format giá tiền theo định dạng VND"""
        if price is None:
            return "N/A"
        return f"{int(price):,}đ".replace(",", ".")


# Singleton instance
_chatbot_instance = None

def get_chatbot():
    """Lấy instance của ChatbotService"""
    global _chatbot_instance
    if _chatbot_instance is None:
        _chatbot_instance = ChatbotService()
    return _chatbot_instance

#!/usr/bin/env python3
"""
DU Bill Fetcher Bot
يجلب الفواتير من موقع du تلقائياً مع حل CAPTCHA
"""

import requests
import json
import time
import re
from typing import Dict, Optional, Tuple
from PIL import Image
from io import BytesIO
import base64

class DUBillBot:
    def __init__(self, captcha_api_key: Optional[str] = None):
        """
        تهيئة البوت
        
        Args:
            captcha_api_key: مفتاح API من 2Captcha (اختياري)
        """
        self.captcha_api_key = captcha_api_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.base_url = "https://myaccount.du.ae"
        self.api_url = "https://myaccount.du.ae/api"
        
    def get_captcha_image(self) -> Optional[Tuple[str, str]]:
        """
        جلب صورة CAPTCHA من موقع du
        
        Returns:
            tuple: (image_base64, captcha_id) أو None إذا فشل
        """
        try:
            # محاولة جلب صورة CAPTCHA
            response = self.session.get(
                f"{self.api_url}/captcha/image",
                timeout=10
            )
            
            if response.status_code == 200:
                # تحويل الصورة إلى base64
                image_base64 = base64.b64encode(response.content).decode('utf-8')
                
                # محاولة الحصول على معرّف CAPTCHA من الـ cookies
                captcha_id = self.session.cookies.get('captcha_id', 'unknown')
                
                return image_base64, captcha_id
        except Exception as e:
            print(f"خطأ في جلب CAPTCHA: {e}")
        
        return None
    
    def solve_captcha_with_2captcha(self, image_base64: str) -> Optional[str]:
        """
        حل CAPTCHA باستخدام خدمة 2Captcha
        
        Args:
            image_base64: صورة CAPTCHA بصيغة base64
            
        Returns:
            الإجابة أو None إذا فشل
        """
        if not self.captcha_api_key:
            print("لم يتم توفير مفتاح 2Captcha API")
            return None
        
        try:
            # إرسال الصورة إلى 2Captcha
            url = "http://2captcha.com/api/upload"
            files = {'captchafile': ('captcha.png', base64.b64decode(image_base64))}
            data = {'key': self.captcha_api_key}
            
            response = requests.post(url, files=files, data=data, timeout=30)
            
            if response.status_code == 200:
                result = response.text
                if result.startswith('OK|'):
                    captcha_id = result.split('|')[1]
                    
                    # الانتظار للحصول على النتيجة
                    for attempt in range(30):  # محاولة 30 مرة (3 دقائق)
                        time.sleep(2)
                        
                        check_url = "http://2captcha.com/api/res"
                        check_data = {'key': self.captcha_api_key, 'action': 'get', 'id': captcha_id}
                        check_response = requests.get(check_url, params=check_data, timeout=10)
                        
                        if check_response.status_code == 200:
                            check_result = check_response.text
                            if check_result.startswith('OK|'):
                                answer = check_result.split('|')[1]
                                return answer
                            elif check_result == 'CAPCHA_NOT_READY':
                                continue
                            else:
                                print(f"خطأ من 2Captcha: {check_result}")
                                return None
        except Exception as e:
            print(f"خطأ في حل CAPTCHA: {e}")
        
        return None
    
    def fetch_bill(self, phone_number: str, captcha_answer: Optional[str] = None) -> Optional[Dict]:
        """
        جلب الفاتورة برقم الهاتف
        
        Args:
            phone_number: رقم الهاتف
            captcha_answer: إجابة CAPTCHA (إذا كانت معروفة)
            
        Returns:
            بيانات الفاتورة أو None إذا فشل
        """
        try:
            # الخطوة 1: إرسال رقم الهاتف
            payload = {
                'mobileNumber': phone_number,
                'captcha': captcha_answer or ''
            }
            
            response = self.session.post(
                f"{self.api_url}/quickpay/bill",
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    return {
                        'success': True,
                        'phone': phone_number,
                        'bill': data.get('bill'),
                        'amount': data.get('amount'),
                        'dueDate': data.get('dueDate'),
                        'status': data.get('status')
                    }
                elif data.get('requiresCaptcha'):
                    # يتطلب حل CAPTCHA
                    return {
                        'success': False,
                        'requiresCaptcha': True,
                        'message': 'يتطلب حل CAPTCHA'
                    }
            
            return {
                'success': False,
                'message': f'خطأ: {response.status_code}',
                'error': response.text
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'خطأ في جلب الفاتورة: {str(e)}'
            }
    
    def fetch_bill_with_auto_captcha(self, phone_number: str) -> Optional[Dict]:
        """
        جلب الفاتورة مع حل CAPTCHA التلقائي
        
        Args:
            phone_number: رقم الهاتف
            
        Returns:
            بيانات الفاتورة أو None إذا فشل
        """
        try:
            # الخطوة 1: محاولة جلب الفاتورة بدون CAPTCHA
            result = self.fetch_bill(phone_number)
            
            if result and result.get('success'):
                return result
            
            # الخطوة 2: إذا كان يتطلب CAPTCHA، جلب صورة CAPTCHA
            if result and result.get('requiresCaptcha'):
                captcha_data = self.get_captcha_image()
                
                if captcha_data:
                    image_base64, captcha_id = captcha_data
                    
                    # الخطوة 3: حل CAPTCHA
                    answer = self.solve_captcha_with_2captcha(image_base64)
                    
                    if answer:
                        # الخطوة 4: محاولة جلب الفاتورة مع الإجابة
                        result = self.fetch_bill(phone_number, answer)
                        return result
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'message': f'خطأ: {str(e)}'
            }


# مثال على الاستخدام
if __name__ == '__main__':
    # استخدام البوت
    bot = DUBillBot(captcha_api_key='YOUR_2CAPTCHA_API_KEY')
    
    # جلب الفاتورة
    result = bot.fetch_bill_with_auto_captcha('971501234567')
    print(json.dumps(result, indent=2, ensure_ascii=False))

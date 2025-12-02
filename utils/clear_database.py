# utils/clear_database.py — С ПОДДЕРЖКОЙ КВОТ FIRESTORE

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import firebase_admin
from firebase_admin import credentials, firestore
import config
import logging
import time
from typing import Tuple

logger = logging.getLogger(__name__)

def delete_all_properties() -> Tuple[int, bool]:
    """
    Удаляет все документы из коллекции properties с учетом квот Firestore.
    Возвращает (количество_удаленных, успешно_завершено).
    """
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)
        
        db = firestore.client()
        collection_ref = db.collection('properties')
        docs = collection_ref.stream()
        
        deleted_count = 0
        batch_size = 200  # Уменьшаем размер батча для снижения нагрузки на квоты
        max_retries = 3
        batch_delay = 2.0  # Задержка между батчами в секундах
        
        print(f"Найдено {sum(1 for _ in docs)} документов для удаления")
        
        # Сбрасываем итератор
        docs = collection_ref.stream()
        
        batch = db.batch()
        
        for doc in docs:
            batch.delete(doc.reference)
            deleted_count += 1
            
            # Выполняем батч каждые 200 документов
            if deleted_count % batch_size == 0:
                success = False
                for attempt in range(max_retries):
                    try:
                        batch.commit()
                        success = True
                        print(f"✓ Удалено {deleted_count} документов (батч {deleted_count//batch_size})")
                        break
                    except Exception as e:
                        if "429" in str(e) or "quota" in str(e).lower():
                            wait_time = batch_delay * (2 ** attempt)  # Экспоненциальная задержка
                            print(f"⚠ Квота превышена. Ждем {wait_time:.1f} сек (попытка {attempt+1}/{max_retries})")
                            time.sleep(wait_time)
                        else:
                            raise e
                
                if not success:
                    print(f"❌ Не удалось выполнить батч после {max_retries} попыток")
                    break
                
                batch = db.batch()
                time.sleep(batch_delay)  # Задержка между батчами
        
        # Выполняем последний батч
        if deleted_count % batch_size != 0:
            success = False
            for attempt in range(max_retries):
                try:
                    batch.commit()
                    success = True
                    print(f"✓ Завершен последний батч ({deleted_count % batch_size} документов)")
                    break
                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower():
                        wait_time = batch_delay * (2 ** attempt)
                        print(f"⚠ Квота превышена. Ждем {wait_time:.1f} сек (попытка {attempt+1}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        raise e
            
            if not success:
                print(f"❌ Не удалось выполнить последний батч после {max_retries} попыток")
        
        print(f"🎉 Операция завершена. Удалено {deleted_count} документов.")
        return deleted_count, True
        
    except Exception as e:
        logger.error(f"Критическая ошибка при удалении документов: {e}")
        print(f"❌ Критическая ошибка: {e}")
        return 0, False

def main():
    """Основная функция для очистки базы данных"""
    print("=== ОЧИСТКА БАЗЫ ДАННЫХ FIRESTORE ===")
    print("⚠️  ВНИМАНИЕ: Эта операция удалит ВСЕ документы из коллекции 'properties'")
    print("⚠️  Операция необратима! Данные будут потеряны навсегда.")
    print()
    
    response = input("Вы уверены, что хотите удалить все документы из коллекции properties? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y', 'да', 'д']:
        print("\n🔄 Начинается очистка базы данных...")
        print("💡 Бот будет удалять документы батчами по 200 штук с паузами для соблюдения квот.")
        print("⏳ Это может занять несколько минут в зависимости от количества документов.")
        print()
        
        deleted_count, success = delete_all_properties()
        
        if success and deleted_count > 0:
            print(f"\n✅ ОПЕРАЦИЯ УСПЕШНО ЗАВЕРШЕНА!")
            print(f"📊 Удалено {deleted_count:,} документов из коллекции properties")
            print("\n🚀 Теперь база чистая и готова для нового парсинга.")
        elif success:
            print(f"\n⚠️  Операция завершена, но документов не найдено.")
            print("📭 Коллекция 'properties' уже пуста.")
        else:
            print(f"\n❌ ОШИБКА ПРИ ВЫПОЛНЕНИИ ОПЕРАЦИИ!")
            print(f"📊 Удалено только {deleted_count:,} документов")
            print("💡 Попробуйте повторить позже или проверьте настройки Firebase.")
    else:
        print("\n❌ Операция отменена пользователем.")

if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    main()
#include "dynamic.h"

template<typename T>
inline bool list<T>::grow(size_t new_capacity)
{
	size_t new_size_bytes = newCapacity * sizeof(T);
	T* new_data = static_cast<T*>(ExAllocatePool2(_poolFlags, new_size_bytes, _tag));

	if (!new_data) {
		return false;
	}

	for (size_t i = 0; i < _size; i++) {
		new_data[i] = _data[i];
	}

	if (_data) {
		ExFreePool(_data);
	}

	_data = new_data;
	_capacity = new_capacity;
}

template<typename T>
list<T>::list(ULONG poolFlags, ULONG tag){}

template<typename T>
list<T>::~list()
{
	clear();
}

template<typename T>
bool list<T>::append(const T& value)
{
	if (_size >= _capacity) {
		size_t new_capacity = (_capacity == 0) : 4 ? _capacity * 2;
		if (!grow(new_capacity)) return false;
	}

	_data[_size++] = value;
	return true;
}

template<typename T>
bool list<T>::remove(size_t index)
{
	if (index >= _size)
		return false;

	// Вызов деструктора, если это объектный тип
	_data[index].~T();

	// Если не последний элемент — сдвигаем оставшиеся
	if (index < _size - 1) {
		RtlMoveMemory(&_data[index], &_data[index + 1], (_size - index - 1) * sizeof(T));
	}

	--_size;
	return true;
}

template<typename T>
T& list<T>::operator[](size_t index)
{
	ASSERT(index < _size)
		return _data[index];
}

template<typename T>
const T& list<T>::operator[](size_t index) const
{
	ASSERT(index < _size)
		return _data[index];
}

template<typename T>
size_t list<T>::size()
{
	return _size;
}

template<typename T>
size_t list<T>::capacity()
{
	return _capacity;
}

template<typename T>
void list<T>::clear()
{
	if (_data) {
		ExFreePool(_data);
		_data = nullptr;
	}
	_size = 0;
	_capacity = 0;
}

template<typename T>
T* list<T>::data()
{
	return _data;
}

template<typename T>
const T* list<T>::data() const
{
	return _data;
}

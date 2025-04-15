#pragma once
#include <ntddk.h>

#define VECTOR_TAG 'VecK'

template <typename T>
class list {
private:
	T* _data = nullptr;
	size_t _size = 0;
	size_t _capacity = 0;
	ULONG _tag = VECTOR_TAG;
	ULONG _poolFlags = POOL_FLAG_NON_PAGED;

	bool grow(size_t new_capacity);

public:
	list(ULONG poolFlags = POOL_FLAG_NON_PAGED, ULONG tag = VECTOR_TAG)
		: _tag(tag), _poolFlags(poolFlags);

	~list();

	bool append(const T& value);

	bool remove(size_t index);

	T& operator[](size_t index);

	const T& operator[](size_t index) const;

	size_t size();

	size_t capacity();

	void clear();

	T* data();

	const T* data() const;
};
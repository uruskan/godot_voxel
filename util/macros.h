#ifndef ZYLANN_MACROS_H
#define ZYLANN_MACROS_H

// Macros I couldn't put anywhere specific

#define ZN_ARRAY_LENGTH(a) (sizeof(a) / sizeof(a[0]))

// Tell the compiler to favour a certain branch of a condition.
// Until C++20 can be used with the [[likely]] and [[unlikely]] attributes.
#if defined(__GNUC__)
#define ZN_LIKELY(x) __builtin_expect(!!(x), 1)
#define ZN_UNLIKELY(x) __builtin_expect(!!(x), 0)
#else
#define ZN_LIKELY(x) x
#define ZN_UNLIKELY(x) x
#endif

#endif // ZYLANN_MACROS_H

# Testing Guide

## Test Structure
- All tests must extend `PaymentTestBase`
- Use JUnit 5 + Mockito
- Mock all external dependencies

## Naming Convention
Format: `methodUnderTest_scenario_expectedResult`

Example:
```java
@Test
void createOrder_nullItems_throwsIllegalArgumentException() { ... }
```

## Running Tests
```bash
mvn test
```

## Coverage Requirements
- Minimum coverage: 30%+
- Focus on exception branches first
- Test all public methods

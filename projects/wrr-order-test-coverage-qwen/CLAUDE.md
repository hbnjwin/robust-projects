# Project Rules

## Testing Standards
- Read `TESTING_GUIDE.md` before modifying any test files
- All new tests must extend `PaymentTestBase`
- Test naming convention: `methodUnderTest_scenario_expectedResult`
- Final response must list all executed test commands
- Mock all external dependencies, never call real services

## Testing
- Run `mvn test` before committing
- Coverage must increase from current 30%+

## Commit
- Commit message format: `test(scope): description`

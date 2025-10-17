import {
  Card,
  CardBody,
  CardHeader,
  Heading,
  Progress,
  SimpleGrid,
  Stack,
  Stat,
  StatHelpText,
  StatLabel,
  StatNumber,
  Text
} from '@chakra-ui/react';

const OperationsOverviewPage = () => (
  <Stack spacing={6}>
    <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
      <Card>
        <CardHeader>
          <Heading size="sm">Storage consumption</Heading>
        </CardHeader>
        <CardBody>
          <Stack spacing={3}>
            <Progress value={78} borderRadius="full" colorScheme="purple" />
            <Text fontSize="sm">7.8 TB of 10 TB allocated</Text>
          </Stack>
        </CardBody>
      </Card>
      <Card>
        <CardHeader>
          <Heading size="sm">Ingest velocity</Heading>
        </CardHeader>
        <CardBody>
          <Stat>
            <StatLabel>Assets ingested last 24h</StatLabel>
            <StatNumber>482</StatNumber>
            <StatHelpText>p95 ingest job duration: 3m 15s</StatHelpText>
          </Stat>
        </CardBody>
      </Card>
      <Card>
        <CardHeader>
          <Heading size="sm">Job queue health</Heading>
        </CardHeader>
        <CardBody>
          <Stat>
            <StatLabel>Merge orchestrator queue</StatLabel>
            <StatNumber>4 pending</StatNumber>
            <StatHelpText color="green.500">No SLA breaches detected</StatHelpText>
          </Stat>
        </CardBody>
      </Card>
    </SimpleGrid>
    <Card>
      <CardHeader>
        <Heading size="sm">Prometheus signals</Heading>
      </CardHeader>
      <CardBody>
        <Stack spacing={2}>
          <Text fontSize="sm">• api_latency_seconds p95 — 612ms</Text>
          <Text fontSize="sm">• review_websocket_connected — 132 sessions</Text>
          <Text fontSize="sm">• storage_reclaim_job_duration p99 — 5m 40s</Text>
        </Stack>
      </CardBody>
    </Card>
  </Stack>
);

export default OperationsOverviewPage;

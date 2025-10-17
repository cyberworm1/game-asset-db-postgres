import { useEffect, useState } from 'react';
import { isAxiosError } from 'axios';
import {
  Alert,
  AlertDescription,
  Badge,
  Card,
  CardBody,
  CardHeader,
  Heading,
  Progress,
  SimpleGrid,
  Spinner,
  Stack,
  Stat,
  StatHelpText,
  StatLabel,
  StatNumber,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr
} from '@chakra-ui/react';
import {
  fetchOpenCueDetails,
  OpenCueDetailedResponse,
  statusToColor
} from '../../lib/rendering';

const OperationsOverviewPage = () => {
  const [renderData, setRenderData] = useState<OpenCueDetailedResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    const load = async () => {
      try {
        const data = await fetchOpenCueDetails();
        if (!ignore) {
          setRenderData(data);
        }
      } catch (err: unknown) {
        if (!ignore) {
          if (isAxiosError(err) && err.response?.status === 403) {
            setError('Admin access required to view OpenCue details.');
          } else {
            setError('Unable to retrieve OpenCue job details.');
          }
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    };

    load();
    return () => {
      ignore = true;
    };
  }, []);

  const renderStatusCard = (
    <Card>
      <CardHeader>
        <Heading size="sm">OpenCue render status</Heading>
      </CardHeader>
      <CardBody>
        {isLoading ? (
          <Stack direction="row" spacing={3} align="center">
            <Spinner size="sm" />
            <Text fontSize="sm">Querying render farm…</Text>
          </Stack>
        ) : error ? (
          <Alert status="warning" borderRadius="md">
            <AlertDescription fontSize="sm">{error}</AlertDescription>
          </Alert>
        ) : renderData ? (
          renderData.enabled && renderData.available ? (
            <Stack spacing={5}>
              <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
                {(
                  [
                    { label: 'Cued', value: renderData.summary.cued, color: 'purple' },
                    { label: 'Running', value: renderData.summary.running, color: 'blue' },
                    { label: 'Success', value: renderData.summary.success, color: 'green' },
                    { label: 'Fail', value: renderData.summary.fail, color: 'red' }
                  ] as const
                ).map((item) => (
                  <Stat key={item.label} borderRadius="lg" borderWidth="1px" padding={3}>
                    <StatLabel>{item.label}</StatLabel>
                    <StatNumber color={`${item.color}.500`}>{item.value}</StatNumber>
                  </Stat>
                ))}
              </SimpleGrid>
              <Table size="sm" variant="striped">
                <Thead>
                  <Tr>
                    <Th>Job</Th>
                    <Th>Show / Shot</Th>
                    <Th>Status</Th>
                    <Th isNumeric>Frames</Th>
                    <Th>Owner</Th>
                    <Th>Started</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {renderData.jobs.slice(0, 12).map((job, index) => (
                    <Tr key={job.id ?? job.name ?? index}>
                      <Td>{job.name ?? job.id ?? '—'}</Td>
                      <Td>
                        <Stack spacing={0} fontSize="sm">
                          <Text>{job.show ?? '—'}</Text>
                          <Text color="gray.500">{job.shot ?? job.layer ?? ''}</Text>
                        </Stack>
                      </Td>
                      <Td>
                        <Badge colorScheme={statusToColor(job.status)} textTransform="capitalize">
                          {job.status}
                        </Badge>
                      </Td>
                      <Td isNumeric>
                        {job.running_frames != null || job.succeeded_frames != null || job.failed_frames != null ? (
                          <Stack spacing={0} align="flex-end" fontSize="xs">
                            <Text>R {job.running_frames ?? 0}</Text>
                            <Text color="green.600">S {job.succeeded_frames ?? 0}</Text>
                            <Text color="red.500">F {job.failed_frames ?? 0}</Text>
                          </Stack>
                        ) : (
                          job.frame_count ?? '—'
                        )}
                      </Td>
                      <Td>{job.user ?? '—'}</Td>
                      <Td>
                        {job.started_at ? new Date(job.started_at).toLocaleString() : '—'}
                      </Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
              <Text fontSize="xs" color="gray.500">
                Last updated {new Date(renderData.last_updated).toLocaleString()} from {renderData.source ?? 'OpenCue'}
              </Text>
            </Stack>
          ) : (
            <Alert status="info" borderRadius="md">
              <AlertDescription fontSize="sm">
                {renderData.message ?? 'OpenCue integration is not enabled.'}
              </AlertDescription>
            </Alert>
          )
        ) : null}
      </CardBody>
    </Card>
  );

  return (
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
      {renderStatusCard}
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
};

export default OperationsOverviewPage;

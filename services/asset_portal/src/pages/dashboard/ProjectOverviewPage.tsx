import {
  Card,
  CardBody,
  CardHeader,
  Heading,
  SimpleGrid,
  Stat,
  StatArrow,
  StatHelpText,
  StatLabel,
  StatNumber,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tr
} from '@chakra-ui/react';

const projectRows = [
  {
    name: 'Project Odyssey',
    assets: 1542,
    backlog: 18,
    throughput: '112 assets/week',
    delta: 12
  },
  {
    name: 'Lego Racing',
    assets: 986,
    backlog: 6,
    throughput: '87 assets/week',
    delta: -4
  },
  {
    name: 'Neon Skies',
    assets: 743,
    backlog: 11,
    throughput: '64 assets/week',
    delta: 6
  }
];

const ProjectOverviewPage = () => (
  <SimpleGrid spacing={6}>
    <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
      <StatCard label="Tracked projects" value="7" helper="vs last month" delta={8} />
      <StatCard label="Assets under review" value="94" helper="Rolling 7 day" delta={-5} />
      <StatCard label="Throughput" value="312 assets/week" helper="Studio-wide" delta={14} />
    </SimpleGrid>
    <Card>
      <CardHeader>
        <Heading size="md">Project portfolio</Heading>
      </CardHeader>
      <CardBody>
        <Table variant="simple" size="md">
          <Thead>
            <Tr>
              <Th>Project</Th>
              <Th isNumeric>Assets</Th>
              <Th isNumeric>Review backlog</Th>
              <Th>Throughput</Th>
              <Th>Trend</Th>
            </Tr>
          </Thead>
          <Tbody>
            {projectRows.map((row) => (
              <Tr key={row.name}>
                <Td>{row.name}</Td>
                <Td isNumeric>{row.assets}</Td>
                <Td isNumeric>{row.backlog}</Td>
                <Td>{row.throughput}</Td>
                <Td>
                  <StatArrow type={row.delta >= 0 ? 'increase' : 'decrease'} />
                  {Math.abs(row.delta)}%
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </CardBody>
    </Card>
  </SimpleGrid>
);

const StatCard = ({
  label,
  value,
  helper,
  delta
}: {
  label: string;
  value: string;
  helper: string;
  delta: number;
}) => (
  <Card>
    <CardHeader>
      <Heading size="sm">{label}</Heading>
    </CardHeader>
    <CardBody>
      <Stat>
        <StatLabel>{helper}</StatLabel>
        <StatNumber>{value}</StatNumber>
        <StatHelpText>
          <StatArrow type={delta >= 0 ? 'increase' : 'decrease'} />
          {Math.abs(delta)}%
        </StatHelpText>
      </Stat>
    </CardBody>
  </Card>
);

export default ProjectOverviewPage;
